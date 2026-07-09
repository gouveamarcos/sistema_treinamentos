from django import forms
from django.contrib.auth.password_validation import validate_password

from .models import Curso, Empresa, Tecnico


class LiberarCursoLoteForm(forms.Form):
    empresa = forms.ModelChoiceField(
        label="Empresa",
        queryset=Empresa.objects.filter(ativa=True).order_by("nome"),
        empty_label="Selecione a empresa",
    )
    curso = forms.ModelChoiceField(
        label="Curso",
        queryset=Curso.objects.filter(ativo=True).select_related("produto").order_by(
            "produto__nome",
            "nome",
        ),
        empty_label="Selecione o curso",
    )
    tecnicos = forms.ModelMultipleChoiceField(
        label="Técnicos",
        queryset=Tecnico.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": "10"}),
    )
    todos_tecnicos = forms.BooleanField(
        label="Liberar para todos os técnicos ativos da empresa",
        required=False,
    )
    obrigatorio = forms.BooleanField(
        label="Curso obrigatório",
        required=False,
        initial=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        empresa_id = self.data.get("empresa") or self.initial.get("empresa")
        if empresa_id:
            self.fields["tecnicos"].queryset = Tecnico.objects.filter(
                empresa_id=empresa_id,
                ativo=True,
            ).order_by("nome")
        else:
            self.fields["tecnicos"].queryset = Tecnico.objects.filter(
                ativo=True,
            ).select_related("empresa").order_by("empresa__nome", "nome")

    def clean(self):
        dados = super().clean()
        empresa = dados.get("empresa")
        tecnicos = dados.get("tecnicos")
        todos_tecnicos = dados.get("todos_tecnicos")

        if not empresa:
            return dados

        if todos_tecnicos:
            dados["tecnicos"] = Tecnico.objects.filter(
                empresa=empresa,
                ativo=True,
            ).order_by("nome")
            return dados

        if not tecnicos:
            raise forms.ValidationError(
                "Selecione ao menos um técnico ou marque a liberação para todos."
            )

        tecnicos_fora_empresa = tecnicos.exclude(empresa=empresa)
        if tecnicos_fora_empresa.exists():
            raise forms.ValidationError(
                "Todos os técnicos selecionados devem pertencer à empresa escolhida."
            )

        return dados


class ValidarCertificadoForm(forms.Form):
    codigo = forms.CharField(
        label="Código do certificado",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "placeholder": "CERT-XXXXXXXX",
                "autocomplete": "off",
            }
        ),
    )

    def clean_codigo(self):
        codigo = self.cleaned_data["codigo"].strip().upper().replace(" ", "")
        if codigo and not codigo.startswith("CERT-"):
            codigo = f"CERT-{codigo}"
        return codigo


class PrimeiroAcessoForm(forms.Form):
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"placeholder": "Digite seu e-mail cadastrado"}),
    )
    matricula = forms.CharField(
        label="Matrícula",
        max_length=50,
        widget=forms.TextInput(attrs={"placeholder": "Digite sua matrícula"}),
    )
    senha = forms.CharField(
        label="Senha",
        validators=[validate_password],
        widget=forms.PasswordInput(attrs={"placeholder": "Crie uma senha"}),
    )
    confirmar_senha = forms.CharField(
        label="Confirmar senha",
        widget=forms.PasswordInput(attrs={"placeholder": "Confirme sua senha"}),
    )

    def clean(self):
        dados = super().clean()
        if dados.get("senha") and dados.get("senha") != dados.get("confirmar_senha"):
            raise forms.ValidationError("As senhas não conferem.")
        return dados
