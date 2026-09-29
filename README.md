# CLASSCONT.ALMOX

Sistema de **almoxarifado** para um órgão público: catálogo de materiais de consumo, entradas por nota fiscal com **custo médio ponderado**, **kardex** imutável, **requisições** dos setores com aprovação da chefia, **cota mensal** por setor, **reserva de saldo**, atendimento total ou parcial, inventário, **curva ABC** e **fechamento mensal**.

- **API REST** em **Django 5.2 LTS + Django REST Framework** (Python 3.13, PostgreSQL 16, JWT)
- **Front separado** em **React + TypeScript + Tailwind CSS**, para servidores e chefias
- **Templates Django** no painel do almoxarifado, no PDF da guia de saída (WeasyPrint) e nos e-mails

![CI](https://github.com/duanjesus/CLASSCONT.ALMOX/actions/workflows/ci.yml/badge.svg)

---

## Arquitetura

```
┌──────────────────────────┐        ┌───────────────────────────────────────────────────┐
│  frontend/ (React + TS)  │  JWT   │  backend/ (Django)                                │
│  servidor · chefia       │ ─────► │  /api/*     DRF: Views → Serializers → Serviços   │
│  Vite + Tailwind         │  JSON  │  /painel/*  CBVs → Forms → Templates Django       │
└──────────────────────────┘        │  PDF        Template → WeasyPrint                 │
                                    │  E-mails    Template → SMTP (Mailpit em dev)      │
   Almoxarifado (navegador) ──────► │                                                   │
   sessão + CSRF                    │  dominio/ (Python puro) ◄── serviços              │
                                    │  ORM ─► PostgreSQL 16 (constraints, FOR UPDATE)   │
                                    └───────────────────────────────────────────────────┘
```

| Camada | Onde | Responsabilidade |
|---|---|---|
| **Domínio** | `backend/dominio/` | Regras em **Python puro**, sem importar Django: custo médio, máquina de estados da requisição, reserva/atendimento, cota, curva ABC, reposição, competência. Testadas sem banco. |
| **Serviços** | `estoque/services.py`, `requisicoes/services.py` | Casos de uso: transação, `SELECT … FOR UPDATE`, chamada da regra pura, gravação do kardex e do histórico, e-mail no `on_commit`. |
| **Models** | `contas/`, `estoque/`, `requisicoes/` | Tabelas, `CheckConstraint`/`UniqueConstraint` no banco, `TextChoices` vindas dos enums do domínio. |
| **API** | `api/` | Views finas do DRF, serializers de leitura (campos explícitos) e de entrada, tratador de erros padronizado. |
| **Painel** | `painel/` + `templates/painel/` | CBVs, ModelForms e formsets, template tags próprias, form renderer (layout dos formulários). |
| **Permissões** | `requisicoes/permissoes.py` | Funções puras `pode_ver`, `pode_avaliar`, `pode_atender`… (o equivalente aos *Voters* do Symfony), usadas pela API, pelo painel e pelos serviços. |

---

## Regras de negócio (bons tópicos de conversa)

**Custo médio ponderado** (`dominio/custo_medio.py`)
```
novo_custo = (qtd_atual × custo_atual + qtd_entrada × custo_entrada) / (qtd_atual + qtd_entrada)
```
- Cada entrada recalcula o custo; **a saída sai pelo custo médio e não o altera**.
- Dinheiro é `Decimal`, nunca `float`: 2 casas para reais e **4 casas para o custo unitário**, para não acumular erro de arredondamento.

**Kardex** (`estoque/models.py → Movimentacao`)
- É a **fonte da verdade** do estoque. Movimentações são **imutáveis**: `save()` numa linha existente e `delete()` levantam erro. Corrige-se com um lançamento de ajuste.
- O saldo gravado no `Material` é um *cache* atualizado na **mesma transação** que grava o kardex. O comando `conferir_saldos` compara os dois (usa `DISTINCT ON`, que é do PostgreSQL).
- O banco também protege: `CHECK (quantidade_em_estoque >= 0)`, NF única por fornecedor, material único por requisição.

**Requisição = máquina de estados** (`dominio/requisicao.py`)
```
RASCUNHO → ENVIADA → APROVADA → ATENDIDA | ATENDIDA_PARCIALMENTE
              │  └→ AGUARDANDO_GESTOR (estourou a cota) → APROVADA
              └→ RECUSADA            (e CANCELADA a partir de rascunho, enviada ou aprovada)
```
- A tabela `TRANSICOES` **é** a regra: o que não está nela é proibido.
- **Ninguém avalia a própria requisição.** A do chefe (ou de setor sem chefe) sobe para o gestor.
- **Rascunho é privado**: nem a chefia nem o almoxarifado o veem (API, painel e listagens) até ser enviado.
- A chefia pode **reduzir** quantidades, nunca aumentar. A recusa exige motivo.

**Reserva e atendimento** (`dominio/atendimento.py`)
- **disponível = físico − reservado.** Ao aprovar, reserva-se o que houver disponível (até o aprovado).
- Ao atender, a requisição pode usar a **própria reserva** mais o saldo livre, nunca a reserva das outras.
- Faltou saldo? **Atendimento parcial**: o restante é liberado e o status vira `ATENDIDA_PARCIALMENTE`.
- **Segregação de funções:** o almoxarife não atende a própria requisição.
- Concorrência: dois almoxarifes atendendo ao mesmo tempo não geram saldo negativo. Os materiais são travados com `SELECT … FOR UPDATE`, **sempre em ordem de id**, o que evita deadlock.

**Cota mensal por setor** (`dominio/cota.py`)
- `utilizado = consumido no mês (saídas) + comprometido (aprovadas ainda não entregues)`.
- Se a aprovação da chefia passa da cota, a requisição vai para `AGUARDANDO_GESTOR`, **sem reservar nada**, e o gestor recebe e-mail.

**Reposição e curva ABC** (`dominio/reposicao.py`, `dominio/curva_abc.py`)
- O material atinge o ponto de reposição quando `disponível ≤ mínimo`. A compra sugerida é `máximo − disponível`, e a cobertura em dias é calculada pelo consumo dos últimos 90 dias.
- Um atendimento que faz o material atingir o mínimo dispara e-mail para o almoxarifado.
- Curva ABC: A = itens que somam 80% do valor consumido, B = até 95%, C = o restante. A classe é decidida pelo acumulado **antes** do item, então o maior item é sempre A.

**Fechamento mensal** (`dominio/competencia.py`)
- Só fecha mês encerrado, **em ordem**, e uma única vez. Mês fechado não aceita lançamento, **nem entrada com data retroativa**.
- O fechamento guarda um retrato do mês: entradas, saídas, ajustes e valor do estoque (calculado **por data**, então uma entrada retroativa não distorce o mês anterior).

**Perfis**

| Perfil | Como é definido | Pode |
|---|---|---|
| Servidor | todo usuário | criar, editar (rascunho), enviar e cancelar as próprias requisições |
| **Chefia** | **derivada**: ser chefe de algum setor (não fica gravada) | avaliar as requisições do seu setor e ver o consumo e a cota |
| Almoxarife | `perfil = ALMOXARIFE` | painel: entradas, atendimento, inventário, cadastros, relatórios |
| Gestor | `perfil = GESTOR` | tudo do almoxarife, mais autorizar estouro de cota, setores, cotas, usuários e fechamento mensal |

**Segurança**
- JWT *stateless* na API e sessão + CSRF no painel.
- **Desativar um usuário corta o acesso na hora**, inclusive com um JWT já emitido: o SimpleJWT confere `is_active` a cada requisição. Usuários não são excluídos, porque há histórico ligado a eles.
- **Força bruta:** 5 tentativas erradas por e-mail + IP a cada minuto, na API e no painel (`contas/limitador.py`).
- API: regra de negócio → **422** com mensagem, permissão → **403**, validação → **400** com o campo (`itens[0].quantidade`). Qualquer outro erro → **500 sem detalhes internos**.

---

## Guia de estudo: Django neste projeto

### Symfony → Django (para quem veio do CLASSCONT.RHFOLHA)

| Symfony | Django | Onde ver |
|---|---|---|
| Entity + Doctrine | `models.Model` + ORM | `estoque/models.py` |
| Migrations (Doctrine) | `makemigrations` / `migrate` | `*/migrations/` |
| Controller | View (função ou **class-based view**) | `painel/views/` |
| Form Type | `forms.Form` / `ModelForm` | `painel/forms.py` |
| Collection de forms | **Formset** (`formset_factory`) | entrada de NF: `painel/forms.py`, `templates/painel/entradas/form.html` |
| Twig | Django Template Language | `templates/` |
| Twig extension | **template tags e filtros** (`templatetags/`) | `painel/templatetags/almox.py` |
| Form theme | **Form renderer** (`FORM_RENDERER`) | `painel/formularios.py`, `templates/painel/form/` |
| Voter | funções de permissão + `BasePermission` do DRF | `requisicoes/permissoes.py`, `api/views.py` |
| `security.yaml` firewalls | `DEFAULT_AUTHENTICATION_CLASSES` (JWT) × sessão | `config/settings.py` |
| API Platform / serializer | **Django REST Framework** | `api/` |
| `#[MapRequestPayload]` DTO | `Serializer` de entrada + `is_valid(raise_exception=True)` | `api/serializers.py` |
| Event subscriber de exceção | `EXCEPTION_HANDLER` do DRF + middleware | `api/excecoes.py`, `painel/middleware.py` |
| Console command | **management command** | `painel/management/commands/` |
| Fixtures | comando `carregar_demo` (usa os serviços reais) | `carregar_demo.py` |
| PHPUnit + DAMA | **pytest-django** (transação por teste) + factory_boy | `tests/` |
| PHPStan | **mypy** + django-stubs | `pyproject.toml` |
| PHP-CS-Fixer | **ruff** (lint + formatação) | `pyproject.toml` |
| EasyAdmin | **Django Admin** (vem pronto) | `*/admin.py`, `/django-admin/` |

### ORM e banco

| Conceito | Onde ver |
|---|---|
| `select_related` (JOIN) × `prefetch_related` (2ª query) contra o N+1 | `api/views.py → RequisicaoViewSet.get_queryset` |
| `select_for_update(of=("self",))` dentro de `transaction.atomic` | `requisicoes/services.py → _travar`, `estoque/services.py → travar_materiais` |
| `transaction.on_commit` (e-mail só depois do COMMIT) | `requisicoes/services.py` |
| `aggregate(Sum(...))`, `annotate`, `Case/When` e `F()` | `estoque/services.py → resumo_competencia`, `api/views.py → ConsumoSetorView` |
| `Q` objects com OR e `F("requisitante")` comparando colunas | `requisicoes/services.py → pendentes_de_avaliacao` |
| `distinct("material_id")` (DISTINCT ON do PostgreSQL) | `estoque/services.py → divergencias_de_saldo` |
| `CheckConstraint` / `UniqueConstraint` / `Index` | `Meta` dos models em `estoque/models.py` |
| `bulk_create` / `bulk_update` | `requisicoes/services.py` |
| Usuário customizado (`AbstractBaseUser`, login por e-mail) | `contas/models.py` |
| `TextChoices` geradas a partir do enum do domínio | `requisicoes/models.py → STATUS_CHOICES` |

### Templates Django (o "Twig" do Python)

| Conceito | Onde ver |
|---|---|
| Herança em 3 níveis (`extends` / `block`) | `base.html` → `painel/layout.html` → `painel/*/…html` |
| Herdar um template **e sobrescrever só um bloco** | `painel/usuarios/lista.html` estende `painel/crud/lista.html` |
| `include … with … only` (partial isolado) | `shared/_itens_requisicao.html`, **o mesmo partial** usado no painel e no PDF |
| **Filtros próprios** (`moeda`, `numero`, `percentual`, `competencia`, `cnpj`, `atributo`) | `painel/templatetags/almox.py` |
| **Inclusion tags** (as "macros": badge, cabeçalho, botão POST com CSRF, paginação, item de menu) | `almox.py` + `templates/painel/tags/` |
| `takes_context=True` (repassar `csrf_token` e `request` para a tag) | `botao_post`, `paginacao`, `link_menu` |
| `{% querystring %}` (Django 5.1+) mantendo os filtros na paginação | `painel/tags/paginacao.html` |
| `{% regroup %}` (agrupar por categoria) | `painel/relatorios/reposicao.html` |
| `{% for … empty %}`, `forloop.last`, `{% with %}`, `{% url … as var %}` | `dashboard.html`, `requisicoes/detalhe.html`, `usuarios/lista.html` |
| Filtros nativos: `date`, `pluralize`, `yesno`, `default`, `capfirst`, `linebreaksbr`, `escapejs` | espalhados pelo painel |
| Formset com `management_form` e `empty_form` (linhas dinâmicas) | `painel/entradas/form.html` |
| **Form renderer**: layout de `{{ form }}` e de cada campo | `painel/formularios.py`, `templates/painel/form/` |
| Context processor (contadores do menu) | `painel/context_processors.py` |
| Template → **PDF** (WeasyPrint, CSS `@page`) | `templates/pdf/`, `requisicoes/pdf.py` |
| Template → **e-mail** (texto + HTML, `EmailMultiAlternatives`) | `templates/emails/`, `requisicoes/notificacoes.py` |
| Tailwind no template **sem Node** (binário standalone) | `assets/painel.css`, `docker/python/Dockerfile` |

### Django REST Framework

| Conceito | Onde ver |
|---|---|
| `GenericViewSet` + mixins + `@action` (`/enviar`, `/aprovar`…) | `api/views.py → RequisicaoViewSet` |
| Router (`DefaultRouter`) | `api/urls.py` |
| Serializer de leitura × serializer de entrada | `api/serializers.py` |
| `BasePermission.has_object_permission` | `api/views.py → PodeVerRequisicao` |
| Paginação (`PageNumberPagination`) | `RequisicaoViewSet.pagination_class` |
| `django-filter` (`FilterSet` com método próprio) | `api/views.py → MaterialFiltro` |
| JWT (SimpleJWT) com login customizado e limite de tentativas | `api/views.py → LoginView` |
| Handler de exceção global | `api/excecoes.py` |
| OpenAPI / Swagger (drf-spectacular) | `/api/docs` |
| A API diz ao front **o que o usuário pode fazer** (`acoes`) | `RequisicaoDetalheSerializer.get_acoes` |

---

## Como rodar

Pré-requisito: **Docker**. Não é preciso ter Python nem Node instalados.

```bash
docker compose up -d
```

Na primeira subida, o container `backend` aplica as migrations, carrega os dados de demonstração e compila o CSS do painel. Acompanhe com `docker compose logs -f backend`.

| Serviço | URL |
|---|---|
| App do servidor/chefia (React) | http://localhost:5174 |
| Painel do almoxarifado (templates Django) | http://localhost:8082/painel/ |
| API + Swagger | http://localhost:8082/api/docs |
| Django Admin | http://localhost:8082/django-admin/ (usuário gestor) |
| Caixa de e-mails (Mailpit) | http://localhost:8026 |

### Usuários de demonstração (senha `senha123`)

| E-mail | Perfil | Onde entra |
|---|---|---|
| `gestor@classcont.local` | Gestor (chefe da SAD) | painel: autoriza estouro de cota, fecha o mês, cadastra setores e usuários |
| `almoxarife@classcont.local` | Almoxarife | painel: fila de atendimento, entradas, inventário, relatórios |
| `chefe.ti@classcont.local` | Chefia da STI | app: aprova as requisições de Ana e Bruno. A dele mesmo sobe para o gestor. |
| `ana@classcont.local` | Servidora da STI | app: tem requisição aprovada (na fila), atendida e um rascunho |
| `bruno@classcont.local` | Servidor da STI | app: tem requisição aguardando a chefia e uma recusada |
| `chefe.financeiro@classcont.local` | Chefia da SOF (cota baixa) | app: vê a cota da SOF estourada |
| `carla@classcont.local` | Servidora da SOF | app: requisição aguardando o gestor e uma atendida **parcialmente** |
| `diego@classcont.local` | Servidor da SGP (setor sem chefe) | app: as requisições dele vão direto para o gestor |

Os dados são gerados **relativos à data atual**: carga inicial no mês retrasado (já **fechado**), consumo no mês passado (aberto, então o gestor vê o aviso para fechar) e movimento no mês atual.

### Comandos úteis

```bash
# Recarregar os dados de demonstração (apaga tudo)
docker compose exec backend python manage.py carregar_demo

# Testes, lint, tipos
docker compose exec backend pytest
docker compose exec backend ruff check . && docker compose exec backend ruff format --check .
docker compose exec backend mypy .

# Conferir se o saldo dos materiais bate com o kardex
docker compose exec backend python manage.py conferir_saldos

# Recompilar o CSS do painel depois de mexer nos templates
docker compose exec backend tailwindcss -i assets/painel.css -o static/painel/painel.css --minify

# Shell do Django (ótimo para explorar o ORM)
docker compose exec backend python manage.py shell
```

> **Por que as dependências ficam na imagem e os caches num volume?** No Windows e no macOS, o bind mount é lento para milhares de arquivos pequenos. O venv fica dentro da imagem, e os caches do ruff, do mypy e do pytest ficam no volume `cache`. Só o código-fonte é montado.

---

## Qualidade

- **149 testes com pytest** (69 unitários e 80 funcionais):
  - *Unitários* (sem banco): custo médio e arredondamento, todas as transições de status, reserva e atendimento parcial, cota, curva ABC, reposição, competência e fechamento, CNPJ e formatação de dinheiro.
  - *Funcionais* (PostgreSQL): serviços de estoque (constraint do banco, kardex imutável, fechamento bloqueando lançamento retroativo), fluxo completo de requisições (ninguém avalia a própria, rascunho privado, cota → gestor, reserva disputada, e-mails), API (JWT, força bruta, usuário desativado com token válido, 400/403/422, PDF), painel (smoke test de **todas** as telas, permissões por perfil, formset, middleware de erros) e a própria carga de demonstração.
- **ruff** (lint + formatação), **mypy** com django-stubs e drf-stubs (**strict** no `dominio/`), `makemigrations --check`.
- **GitHub Actions**: backend (com Postgres) e frontend (oxlint + build) a cada push.

## Estrutura

```
backend/
  dominio/            regras puras (sem Django)
  contas/             usuário (login por e-mail), setor, perfis, limitador de login
  estoque/            materiais, entradas, kardex, fechamento, relatórios
  requisicoes/        requisição, itens, histórico, permissões, serviços, e-mails, PDF
  api/                DRF: views, serializers, tratamento de erros
  painel/             views (CBV), forms, template tags, middleware, comandos
  templates/          painel/, shared/, pdf/, emails/
  tests/unit | tests/functional
frontend/
  src/pages/          Início, Nova requisição, Minhas requisições, Detalhe/Avaliação, Aprovações, Consumo do setor
  src/api/            cliente axios + tipos do contrato da API
docker/python/        Dockerfile (Python 3.13, WeasyPrint, Tailwind standalone) e entrypoint
```

---

## Roteiro para a entrevista

### Apresentação em 1 minuto
> "É o almoxarifado de um órgão público. Os setores pedem material pelo app React, a chefia aprova respeitando uma cota mensal, e o almoxarifado entrega pelo painel em templates Django. O estoque é valorado pelo custo médio ponderado, e todo movimento vai para um kardex imutável. Separei as regras num pacote de Python puro, testado sem banco. Os serviços cuidam de transação e concorrência, e a API e o painel são camadas finas por cima. Tem 149 testes, mypy e ruff, e roda com um `docker compose up`."

### Demonstração em 5 minutos
1. **App como `bruno`**: criar uma requisição com toner e papel, e enviar.
2. **App como `chefe.ti`**: em Aprovações, reduzir uma quantidade e aprovar. A barra mostra o impacto na cota. A requisição que o próprio chefe fez (toner do gabinete) **não** aparece na lista dele, porque ela vai para o gestor.
3. **Painel como `almoxarife`**: a fila de atendimento já traz o máximo possível preenchido. Atender, abrir a **guia em PDF**, ver o **kardex** do material e o e-mail no **Mailpit**.
4. **App como `carla`**: a requisição dela (cerca de R$ 658) passa da cota de R$ 600 da SOF. A chefia aprovou, mas ela ficou "Aguardando gestor", com o aviso e a nota no histórico mostrando o excedente.
5. **Painel como `gestor`**: em "Autorizações (cota)", autorizar a requisição da Carla. Depois abrir a **curva ABC** e **fechar o mês passado**. Por fim, tentar lançar uma NF com data desse mês: é bloqueado.

### Perguntas prováveis (e respostas curtas)

- **Por que Django e não FastAPI?** Porque o sistema é CRUD administrativo com painel: ORM, migrations, admin, forms, templates e autenticação vêm prontos. O FastAPI brilha em APIs assíncronas e enxutas, mas eu teria de montar tudo isso à mão. Como as regras ficam em `dominio/`, elas iriam para um FastAPI sem mudança.
- **Como você evita estoque negativo com dois atendimentos simultâneos?** Com `transaction.atomic` + `select_for_update` nos materiais, sempre em ordem de id para não dar deadlock, a regra pura `com_saida` que recusa saldo insuficiente e, por último, o `CHECK (quantidade_em_estoque >= 0)` no banco.
- **Por que guardar saldo no material se o kardex já tem tudo?** Por desempenho: a listagem não precisa somar o kardex. O cache é atualizado na mesma transação, e o `conferir_saldos` audita. Se divergir, o kardex vence.
- **O que é o N+1 e onde você tratou?** Uma query por linha ao acessar relacionamentos. Tratei com `select_related` (FK, via JOIN) e `prefetch_related` (listas, via 2ª query), por exemplo na listagem de requisições e no detalhe.
- **Por que `on_commit` para o e-mail?** Se a transação der rollback, o e-mail não pode ter saído. Uma falha de SMTP também não derruba a operação: fica registrada no log.
- **Por que `Decimal` e 4 casas no custo?** `float` não representa centavos com exatidão. Com 4 casas no custo unitário, o erro não se acumula a cada entrada. O valor em reais é arredondado para 2 casas (ROUND_HALF_UP).
- **Como a chefia é definida?** É derivada de o usuário ser chefe de algum setor e não fica gravada em lugar nenhum. Trocou o chefe no cadastro, o papel acompanha na hora.
- **Por que as funções de permissão são puras?** Para usar a mesma regra na API (403), no painel (403 e botões) e nos serviços (defesa em profundidade), e testar sem HTTP. O front recebe `acoes` e só desenha o que o back vai aceitar.
- **Como testar sem que um teste afete o outro?** O pytest-django abre uma transação por teste e faz rollback no fim. As fábricas (factory_boy) montam o cenário, e o cache do limitador é limpo em cada teste.

### O que eu faria em produção
Gunicorn + Nginx com `collectstatic`, Redis para o cache do limitador (o `LocMemCache` é por processo), filas (Celery ou RQ) para e-mail e PDF, *refresh token* com rotação e blacklist, auditoria com `django-simple-history` nos cadastros, e trigger no banco garantindo a imutabilidade do kardex (o `save()` protege o ORM, mas não um `UPDATE` direto).
