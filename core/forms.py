from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

from .models import (
    Alternativa,
    Curso,
    Empresa,
    EtapaCurso,
    Produto,
    Questao,
    ResponsavelEmpresa,
    Tecnico,
)
from .scopes import empresas_do_usuario


def cursos_disponiveis_para_empresas(empresas):
    return Curso.objects.filter(
        ativo=True,
        produto__ativo=True,
        produto__empresa__in=empresas,
    ).select_related("produto").distinct()


def _validar_upload_csv(arquivo):
    if not arquivo.name.lower().endswith(".csv"):
        raise forms.ValidationError("Envie um arquivo CSV.")

    limite = _limite_upload_csv()
    if arquivo.size > limite:
        raise forms.ValidationError(
            f"Arquivo CSV muito grande. Limite: {_texto_limite_upload_csv()}."
        )

    return arquivo


def _limite_upload_csv():
    return getattr(settings, "MAX_CSV_IMPORT_SIZE_BYTES", 2 * 1024 * 1024)


def _texto_limite_upload_csv():
    limite_mb = _limite_upload_csv() / 1024 / 1024
    return f"{limite_mb:.1f} MB"


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

    def __init__(self, *args, usuario=None, empresa_contexto=None, **kwargs):
        super().__init__(*args, **kwargs)
        empresas = (
            Empresa.objects.filter(ativa=True)
            if usuario is None
            else empresas_do_usuario(usuario)
        )
        if empresa_contexto is not None:
            empresas = empresas.filter(pk=empresa_contexto.pk)
        self.fields["empresa"].queryset = empresas.order_by("nome")

        empresa_id = self.data.get("empresa") or self.initial.get("empresa")
        cursos = cursos_disponiveis_para_empresas(empresas)
        tecnicos = Tecnico.objects.filter(ativo=True, empresa__in=empresas)
        if empresa_id:
            filtro_empresa = (
                {"empresa": empresa_id}
                if isinstance(empresa_id, Empresa)
                else {"empresa_id": empresa_id}
            )
            filtro_curso = (
                {"produto__empresa": empresa_id}
                if isinstance(empresa_id, Empresa)
                else {"produto__empresa_id": empresa_id}
            )
            tecnicos = tecnicos.filter(**filtro_empresa)
            cursos = cursos.filter(**filtro_curso)
            self.fields["tecnicos"].queryset = tecnicos.order_by("nome")
        else:
            self.fields["tecnicos"].queryset = tecnicos.select_related(
                "empresa"
            ).order_by("empresa__nome", "nome")
        self.fields["curso"].queryset = cursos.order_by("produto__nome", "nome")

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


class ResponsavelEmpresaForm(forms.Form):
    empresa = forms.ModelChoiceField(
        label="Empresa",
        queryset=Empresa.objects.none(),
        empty_label="Selecione a empresa",
    )
    nome = forms.CharField(
        label="Nome",
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Nome do responsÃ¡vel"}),
    )
    email = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"placeholder": "responsavel@empresa.com.br"}),
    )
    papel = forms.ChoiceField(
        label="Papel",
        choices=ResponsavelEmpresa.Papel.choices,
    )
    ativo = forms.BooleanField(
        label="ResponsÃ¡vel ativo",
        required=False,
        initial=True,
    )

    def __init__(
        self,
        *args,
        usuario=None,
        instance=None,
        empresa_contexto=None,
        **kwargs,
    ):
        self.instance = instance
        self.usuario = usuario
        super().__init__(*args, **kwargs)
        if usuario and usuario.is_superuser and instance is None:
            self.fields["todas_empresas"] = forms.BooleanField(
                label="Cadastrar para todas as empresas ativas",
                required=False,
                help_text=(
                    "Use esta opcao quando a mesma pessoa deve atuar em todas "
                    "as empresas cadastradas."
                ),
            )
        empresas = (
            Empresa.objects.filter(ativa=True)
            if usuario is None
            else empresas_do_usuario(usuario)
        )
        if empresa_contexto is not None:
            empresas = empresas.filter(pk=empresa_contexto.pk)
        self.fields["empresa"].queryset = empresas.order_by("nome")

        if instance and not self.is_bound:
            self.initial.update(
                {
                    "empresa": instance.empresa,
                    "nome": instance.usuario.get_full_name()
                    or instance.usuario.first_name
                    or instance.usuario.username,
                    "email": instance.usuario.email or instance.usuario.username,
                    "papel": instance.papel,
                    "ativo": instance.ativo,
                }
            )

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean(self):
        dados = super().clean()
        empresa = dados.get("empresa")
        email = dados.get("email")
        papel = dados.get("papel")

        if not empresa or not email or not papel:
            return dados

        usuario = User.objects.filter(email__iexact=email).first()
        email_atual = self.instance.usuario.email if self.instance else ""
        if not usuario and email_atual and email_atual.lower() == email:
            usuario = self.instance.usuario

        if usuario:
            existente = ResponsavelEmpresa.objects.filter(
                empresa=empresa,
                usuario=usuario,
                papel=papel,
            )
            if self.instance:
                existente = existente.exclude(pk=self.instance.pk)
            if existente.exists():
                raise forms.ValidationError(
                    "Este usuÃ¡rio jÃ¡ possui esse papel para a empresa escolhida."
                )

        return dados

    def save(self):
        nome = self.cleaned_data["nome"].strip()
        email = self.cleaned_data["email"]
        empresa = self.cleaned_data["empresa"]
        papel = self.cleaned_data["papel"]
        ativo = self.cleaned_data["ativo"]

        usuario = User.objects.filter(email__iexact=email).first()
        if not usuario:
            username_base = email
            username = username_base
            contador = 2
            while User.objects.filter(username=username).exists():
                username = f"{username_base}-{contador}"
                contador += 1
            usuario = User(username=username, email=email)
            usuario.set_unusable_password()

        usuario.email = email
        usuario.first_name = nome[:150]
        usuario.is_active = True
        usuario.is_staff = True
        usuario.save()

        if self.instance:
            responsabilidade = self.instance
            responsabilidade.empresa = empresa
            responsabilidade.usuario = usuario
            responsabilidade.papel = papel
            responsabilidade.ativo = ativo
            responsabilidade.save()
            return responsabilidade

        return ResponsavelEmpresa.objects.create(
            empresa=empresa,
            usuario=usuario,
            papel=papel,
            ativo=ativo,
        )


class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = (
            "nome",
            "documento",
            "responsavel",
            "email",
            "telefone",
            "ativa",
        )
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Nome da empresa"}),
            "documento": forms.TextInput(attrs={"placeholder": "CNPJ ou documento"}),
            "responsavel": forms.TextInput(attrs={"placeholder": "Contato principal"}),
            "email": forms.EmailInput(attrs={"placeholder": "contato@empresa.com.br"}),
            "telefone": forms.TextInput(attrs={"placeholder": "(00) 00000-0000"}),
        }


class TecnicoForm(forms.ModelForm):
    class Meta:
        model = Tecnico
        fields = (
            "empresa",
            "nome",
            "email",
            "matricula",
            "telefone",
            "equipe",
            "regiao",
            "ativo",
        )
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Nome do tecnico"}),
            "email": forms.EmailInput(attrs={"placeholder": "tecnico@empresa.com.br"}),
            "matricula": forms.TextInput(attrs={"placeholder": "Matricula"}),
            "telefone": forms.TextInput(attrs={"placeholder": "(00) 00000-0000"}),
            "equipe": forms.TextInput(attrs={"placeholder": "Equipe"}),
            "regiao": forms.TextInput(attrs={"placeholder": "Regiao"}),
        }

    def __init__(self, *args, usuario=None, empresa_contexto=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.usuario = usuario
        if usuario and usuario.is_superuser and self.instance.pk is None:
            self.fields["todas_empresas"] = forms.BooleanField(
                label="Cadastrar para todas as empresas ativas",
                required=False,
                help_text=(
                    "A plataforma replicara este tecnico nas demais empresas "
                    "ativas com e-mail e matricula identificados por empresa."
                ),
            )
        empresas = (
            Empresa.objects.filter(ativa=True)
            if usuario is None
            else empresas_do_usuario(usuario)
        )
        if empresa_contexto is not None:
            empresas = empresas.filter(pk=empresa_contexto.pk)
        self.fields["empresa"].queryset = empresas.order_by("nome")


class ImportarTecnicosForm(forms.Form):
    empresa = forms.ModelChoiceField(
        label="Empresa",
        queryset=Empresa.objects.none(),
        empty_label="Selecione a empresa",
    )
    arquivo = forms.FileField(
        label="Arquivo CSV",
        help_text=(
            "Use as colunas: nome,email,matricula,telefone,equipe,regiao,ativo. "
            f"Limite: {_texto_limite_upload_csv()}."
        ),
    )

    def __init__(self, *args, usuario=None, empresa_contexto=None, **kwargs):
        super().__init__(*args, **kwargs)
        empresas = (
            Empresa.objects.filter(ativa=True)
            if usuario is None
            else empresas_do_usuario(usuario)
        )
        if empresa_contexto is not None:
            empresas = empresas.filter(pk=empresa_contexto.pk)
        self.fields["empresa"].queryset = empresas.order_by("nome")

    def clean_arquivo(self):
        return _validar_upload_csv(self.cleaned_data["arquivo"])


class ImportarLiberacoesForm(forms.Form):
    empresa = forms.ModelChoiceField(
        label="Empresa",
        queryset=Empresa.objects.none(),
        empty_label="Selecione a empresa",
    )
    curso = forms.ModelChoiceField(
        label="Curso",
        queryset=Curso.objects.none(),
        empty_label="Selecione o curso",
    )
    arquivo = forms.FileField(
        label="Arquivo CSV",
        help_text=(
            "Use as colunas: matricula,email,obrigatorio. "
            f"Limite: {_texto_limite_upload_csv()}."
        ),
    )
    obrigatorio = forms.BooleanField(
        label="Curso obrigatorio quando a coluna obrigatorio estiver vazia",
        required=False,
        initial=True,
    )

    def __init__(self, *args, usuario=None, empresa_contexto=None, **kwargs):
        super().__init__(*args, **kwargs)
        empresas = (
            Empresa.objects.filter(ativa=True)
            if usuario is None
            else empresas_do_usuario(usuario)
        )
        if empresa_contexto is not None:
            empresas = empresas.filter(pk=empresa_contexto.pk)
        self.fields["empresa"].queryset = empresas.order_by("nome")
        cursos = cursos_disponiveis_para_empresas(empresas)
        empresa_id = self.data.get("empresa") or self.initial.get("empresa")
        if empresa_id:
            filtro_curso = (
                {"produto__empresa": empresa_id}
                if isinstance(empresa_id, Empresa)
                else {"produto__empresa_id": empresa_id}
            )
            cursos = cursos.filter(**filtro_curso)
        self.fields["curso"].queryset = cursos.order_by("produto__nome", "nome")

    def clean_arquivo(self):
        return _validar_upload_csv(self.cleaned_data["arquivo"])


class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ("nome", "descricao", "ativo")
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Nome do produto"}),
            "descricao": forms.Textarea(
                attrs={"placeholder": "Descricao breve", "rows": 4}
            ),
        }


class CursoForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = (
            "produto",
            "nome",
            "descricao",
            "validade_meses",
            "nota_minima",
            "link_notebooklm",
            "material_pdf",
            "ativo",
        )
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Nome do curso"}),
            "descricao": forms.Textarea(
                attrs={"placeholder": "Objetivo e resumo do curso", "rows": 4}
            ),
            "link_notebooklm": forms.URLInput(
                attrs={"placeholder": "https://notebooklm.google.com/..."}
            ),
        }

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        produtos = Produto.objects.filter(ativo=True)
        if empresa is not None:
            produtos = produtos.filter(empresa=empresa)
        self.fields["produto"].queryset = produtos.order_by("nome")

    def clean_material_pdf(self):
        arquivo = self.cleaned_data.get("material_pdf")
        if not arquivo:
            return arquivo
        if not arquivo.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Envie um arquivo PDF.")
        limite = 20 * 1024 * 1024
        if arquivo.size > limite:
            raise forms.ValidationError("Arquivo PDF muito grande. Limite: 20 MB.")
        return arquivo


class EtapaCursoForm(forms.ModelForm):
    class Meta:
        model = EtapaCurso
        fields = (
            "titulo",
            "descricao",
            "tipo",
            "ordem",
            "conteudo",
            "video_url",
            "ativo",
        )
        widgets = {
            "titulo": forms.TextInput(attrs={"placeholder": "Titulo da etapa"}),
            "descricao": forms.Textarea(
                attrs={"placeholder": "Resumo da etapa", "rows": 3}
            ),
            "conteudo": forms.Textarea(
                attrs={"placeholder": "Conteudo em texto", "rows": 6}
            ),
            "video_url": forms.URLInput(attrs={"placeholder": "https://..."}),
        }


class QuestaoForm(forms.ModelForm):
    class Meta:
        model = Questao
        fields = ("enunciado", "ordem")
        widgets = {
            "enunciado": forms.Textarea(
                attrs={"placeholder": "Enunciado da questao", "rows": 4}
            ),
        }


class AlternativaForm(forms.ModelForm):
    class Meta:
        model = Alternativa
        fields = ("texto", "correta", "ordem")
        widgets = {
            "texto": forms.TextInput(attrs={"placeholder": "Texto da alternativa"}),
        }


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
