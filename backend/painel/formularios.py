"""Aparência dos formulários do painel.

- ``RendererPainel`` troca os templates que o Django usa para desenhar um
  ``<form>`` e cada campo (``{{ form }}`` e ``{{ campo.as_field_group }}``).
  É o equivalente ao *form theme* do Twig/Symfony.
- ``EstiloMixin`` aplica as classes do Tailwind nos widgets.
"""

from __future__ import annotations

from typing import Any

from django import forms
from django.forms.renderers import TemplatesSetting

CLASSE_CAMPO = (
    "block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm "
    "focus:border-marca-500 focus:outline-none focus:ring-2 focus:ring-marca-500/30 "
    "aria-invalid:border-red-400 aria-invalid:ring-red-200"
)
CLASSE_CHECKBOX = "h-4 w-4 rounded border-slate-300 accent-marca-600"


class RendererPainel(TemplatesSetting):
    form_template_name = "painel/form/form.html"
    field_template_name = "painel/form/campo.html"


class EstiloMixin:
    """Mixin para ``forms.Form``/``ModelForm``: classes CSS e rótulos sem dois-pontos."""

    fields: dict[str, forms.Field]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("label_suffix", "")
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            classe = CLASSE_CHECKBOX if isinstance(widget, forms.CheckboxInput) else CLASSE_CAMPO
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {classe}".strip()
            if isinstance(widget, forms.Textarea):
                widget.attrs["rows"] = 3
