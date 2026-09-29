from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from contas import limitador
from contas.models import Setor, Usuario
from dominio.cnpj import cnpj_valido, somente_digitos
from estoque.models import Categoria, Fornecedor, Material
from painel.formularios import EstiloMixin

# --- Login ----------------------------------------------------------------------


class FormLogin(EstiloMixin, AuthenticationForm):
    """Login do painel: limita tentativas erradas e barra quem não é do almoxarifado."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "E-mail ou senha inválidos.",
    }

    def clean(self) -> dict[str, Any]:
        email = str(self.cleaned_data.get("username") or "").strip().lower()
        self.cleaned_data["username"] = email
        assert self.request is not None
        chave = limitador.chave_login(email, self.request)
        if limitador.bloqueado(chave):
            raise ValidationError(limitador.MENSAGEM_BLOQUEIO, code="bloqueado")
        try:
            dados = super().clean()
        except ValidationError as erro:
            if erro.code == "invalid_login":
                limitador.registrar_falha(chave)
            raise
        limitador.limpar(chave)
        return dados

    def confirm_login_allowed(self, user: Any) -> None:
        super().confirm_login_allowed(user)
        if not user.acessa_painel:
            raise ValidationError(
                "O painel é exclusivo do almoxarifado. Servidores e chefias usam o app de requisições.",
                code="sem_acesso",
            )


# --- Cadastros ------------------------------------------------------------------


class CategoriaForm(EstiloMixin, forms.ModelForm[Categoria]):
    class Meta:
        model = Categoria
        fields = ["nome"]


class MaterialForm(EstiloMixin, forms.ModelForm[Material]):
    class Meta:
        model = Material
        fields = ["codigo", "descricao", "categoria", "unidade", "estoque_minimo", "estoque_maximo", "ativo"]
        help_texts = {
            "estoque_minimo": "Ponto de reposição. Zero = não controlar.",
            "estoque_maximo": "Teto para compra e para o que se pode pedir numa requisição.",
        }

    def clean_codigo(self) -> str:
        return str(self.cleaned_data["codigo"]).strip().upper()

    def clean(self) -> dict[str, Any]:
        dados = super().clean() or {}
        minimo, maximo = dados.get("estoque_minimo"), dados.get("estoque_maximo")
        if minimo is not None and maximo is not None and maximo < minimo:
            self.add_error("estoque_maximo", "O estoque máximo não pode ser menor que o mínimo.")
        return dados


class FornecedorForm(EstiloMixin, forms.ModelForm[Fornecedor]):
    # O model guarda só os 14 dígitos; o formulário aceita o CNPJ com máscara
    cnpj = forms.CharField(label="CNPJ", max_length=18)

    class Meta:
        model = Fornecedor
        fields = ["razao_social", "cnpj", "email", "telefone", "ativo"]

    def clean_cnpj(self) -> str:
        cnpj = str(self.cleaned_data["cnpj"])
        if not cnpj_valido(cnpj):
            raise ValidationError("CNPJ inválido.")
        return somente_digitos(cnpj)


class SetorForm(EstiloMixin, forms.ModelForm[Setor]):
    class Meta:
        model = Setor
        fields = ["sigla", "nome", "chefe", "cota_mensal"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        chefe = self.fields["chefe"]
        assert isinstance(chefe, forms.ModelChoiceField)
        chefe.queryset = Usuario.objects.filter(is_active=True)


class UsuarioForm(EstiloMixin, forms.ModelForm[Usuario]):
    class Meta:
        model = Usuario
        fields = ["nome", "email", "matricula", "cargo", "setor", "perfil"]

    def clean_email(self) -> str:
        return str(self.cleaned_data["email"]).strip().lower()


class UsuarioNovoForm(UsuarioForm):
    senha = forms.CharField(widget=forms.PasswordInput, help_text="O servidor pode trocá-la depois.")

    def clean_senha(self) -> str:
        senha = str(self.cleaned_data["senha"])
        validate_password(senha)
        return senha

    def save(self, commit: bool = True) -> Usuario:
        usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["senha"])
        if commit:
            usuario.save()
        return usuario


# --- Entrada de material (formulário + formset) -----------------------------------


class EntradaForm(EstiloMixin, forms.Form):
    fornecedor = forms.ModelChoiceField(queryset=Fornecedor.objects.filter(ativo=True))
    numero_nota = forms.CharField(label="Nº da nota fiscal", max_length=20)
    data_recebimento = forms.DateField(
        label="Data de recebimento", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    empenho = forms.CharField(label="Nota de empenho", max_length=20, required=False)
    observacao = forms.CharField(label="Observação", widget=forms.Textarea, required=False)

    def clean_data_recebimento(self) -> date:
        dia: date = self.cleaned_data["data_recebimento"]
        if dia > timezone.localdate():
            raise ValidationError("A data de recebimento não pode ser futura.")
        return dia


class ItemEntradaForm(EstiloMixin, forms.Form):
    material = forms.ModelChoiceField(queryset=Material.objects.filter(ativo=True).order_by("descricao"))
    quantidade = forms.IntegerField(min_value=1)
    valor_unitario = forms.DecimalField(
        label="Valor unitário (R$)", min_value=Decimal("0.01"), max_digits=12, decimal_places=2
    )


class BaseItensEntradaFormSet(forms.BaseFormSet[ItemEntradaForm]):
    def clean(self) -> None:
        if any(self.errors):
            return
        vistos: set[int] = set()
        for form in self.forms:
            material = form.cleaned_data.get("material")
            if material is None:
                continue
            if material.pk in vistos:
                raise ValidationError("O mesmo material aparece em duas linhas: some as quantidades.")
            vistos.add(material.pk)


ItensEntradaFormSet = forms.formset_factory(
    ItemEntradaForm, formset=BaseItensEntradaFormSet, extra=0, min_num=1, validate_min=True
)


# --- Estoque e requisições --------------------------------------------------------


class AjusteForm(EstiloMixin, forms.Form):
    quantidade_contada = forms.IntegerField(label="Quantidade contada", min_value=0)
    justificativa = forms.CharField(
        widget=forms.Textarea, min_length=10, help_text="Ex.: “Inventário trimestral: 2 caixas avariadas.”"
    )


class RecusaForm(EstiloMixin, forms.Form):
    motivo = forms.CharField(widget=forms.Textarea, min_length=5)


class AtendimentoForm(forms.Form):
    """Um campo por item, criado dinamicamente, com o máximo atendível como teto."""

    def __init__(self, *args: Any, itens: list[tuple[int, str, int]], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for item_id, rotulo, maximo in itens:
            self.fields[f"item_{item_id}"] = forms.IntegerField(
                label=rotulo,
                min_value=0,
                max_value=maximo,
                initial=maximo,
                widget=forms.NumberInput(
                    attrs={"class": "w-24 rounded-lg border border-slate-300 px-2 py-1 text-right text-sm"}
                ),
            )

    def quantidades(self) -> dict[int, int]:
        return {int(nome.removeprefix("item_")): valor for nome, valor in self.cleaned_data.items()}


# --- Filtros (GET) --------------------------------------------------------------


class FiltroMateriaisForm(EstiloMixin, forms.Form):
    busca = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"placeholder": "Código ou descrição"})
    )
    categoria = forms.ModelChoiceField(queryset=Categoria.objects.all(), required=False, empty_label="Todas")
    situacao = forms.ChoiceField(
        required=False,
        choices=[("", "Todos"), ("repor", "No ponto de reposição"), ("inativos", "Inativos")],
    )


class PeriodoForm(EstiloMixin, forms.Form):
    inicio = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    fim = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))

    @staticmethod
    def padrao() -> dict[str, date]:
        hoje = timezone.localdate()
        return {"inicio": hoje - timedelta(days=89), "fim": hoje}

    def clean(self) -> dict[str, Any]:
        dados = super().clean() or {}
        if dados.get("inicio") and dados.get("fim") and dados["inicio"] > dados["fim"]:
            raise ValidationError("O início do período não pode ser depois do fim.")
        return dados
