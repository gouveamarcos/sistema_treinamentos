from django import forms
from django.contrib.auth.password_validation import validate_password


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
