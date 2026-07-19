import secrets

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from dateutil.relativedelta import relativedelta


class Empresa(models.Model):
    nome = models.CharField(max_length=150, unique=True)
    documento = models.CharField(max_length=30, blank=True)
    responsavel = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    ativa = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("nome",)

    def __str__(self):
        return self.nome


class EventoAuditoria(models.Model):
    class Acao(models.TextChoices):
        CADASTRO = "cadastro", "Cadastro"
        EDICAO = "edicao", "Edicao"
        STATUS = "status", "Status"
        IMPORTACAO = "importacao", "Importacao"
        LIBERACAO = "liberacao", "Liberacao"
        CONVITE = "convite", "Convite"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos_auditoria",
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos_auditoria",
    )
    acao = models.CharField(max_length=20, choices=Acao.choices)
    alvo_tipo = models.CharField(max_length=80)
    alvo_id = models.PositiveIntegerField(null=True, blank=True)
    alvo_repr = models.CharField(max_length=255, blank=True)
    detalhes = models.TextField(blank=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-criado_em", "-id")
        verbose_name = "Evento de auditoria"
        verbose_name_plural = "Eventos de auditoria"

    def __str__(self):
        return f"{self.get_acao_display()} - {self.alvo_repr or self.alvo_tipo}"


class ResponsavelEmpresa(models.Model):
    class Papel(models.TextChoices):
        OPERACIONAL = "operacional", "Responsável operacional"
        EDITOR_CURSOS = "editor_cursos", "Editor de cursos"

    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name="responsaveis"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="responsabilidades_empresas",
    )
    papel = models.CharField(
        max_length=20, choices=Papel.choices, default=Papel.OPERACIONAL
    )
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("empresa__nome", "usuario__username")
        verbose_name = "Responsável da empresa"
        verbose_name_plural = "Responsáveis das empresas"
        constraints = [
            models.UniqueConstraint(
                fields=("empresa", "usuario", "papel"),
                name="responsavel_empresa_papel_unico",
            )
        ]

    def __str__(self):
        return f"{self.usuario} - {self.empresa} ({self.get_papel_display()})"

    @property
    def nome_grupo(self):
        return {
            self.Papel.OPERACIONAL: "Responsável operacional",
            self.Papel.EDITOR_CURSOS: "Editor de cursos",
        }[self.papel]

    def save(self, *args, **kwargs):
        papel_anterior = None
        ativo_anterior = None
        if self.pk:
            anterior = type(self).objects.filter(pk=self.pk).first()
            if anterior:
                papel_anterior = anterior.papel
                ativo_anterior = anterior.ativo

        super().save(*args, **kwargs)
        self._sincronizar_grupos(papel_anterior, ativo_anterior)

    def delete(self, *args, **kwargs):
        usuario = self.usuario
        papel = self.papel
        resultado = super().delete(*args, **kwargs)
        self._remover_grupo_se_sem_responsabilidade(usuario, papel)
        return resultado

    def _sincronizar_grupos(self, papel_anterior, ativo_anterior):
        from django.contrib.auth.models import Group

        if self.ativo:
            grupo = Group.objects.filter(name=self.nome_grupo).first()
            if grupo:
                self.usuario.groups.add(grupo)

        papel_mudou = papel_anterior and papel_anterior != self.papel
        desativou = ativo_anterior is True and not self.ativo
        if papel_mudou or desativou:
            self._remover_grupo_se_sem_responsabilidade(
                self.usuario,
                papel_anterior,
            )

    @classmethod
    def _remover_grupo_se_sem_responsabilidade(cls, usuario, papel):
        from django.contrib.auth.models import Group

        if not papel:
            return

        ainda_tem_papel = cls.objects.filter(
            usuario=usuario,
            papel=papel,
            ativo=True,
        ).exists()
        if ainda_tem_papel:
            return

        nome_grupo = {
            cls.Papel.OPERACIONAL: "Responsável operacional",
            cls.Papel.EDITOR_CURSOS: "Editor de cursos",
        }[papel]
        grupo = Group.objects.filter(name=nome_grupo).first()
        if grupo:
            usuario.groups.remove(grupo)


class Produto(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome


class Tecnico(models.Model):
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="tecnicos",
    )
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="tecnico",
    )
    nome = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    matricula = models.CharField(max_length=50, unique=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    equipe = models.CharField(max_length=100, blank=True, null=True)
    regiao = models.CharField(max_length=100, blank=True, null=True)
    ativo = models.BooleanField(default=True)

    def __str__(self):
        return self.nome


class Curso(models.Model):
    nome = models.CharField(max_length=150)
    descricao = models.TextField(blank=True, null=True)
    produto = models.ForeignKey(
        Produto, on_delete=models.PROTECT, related_name="cursos"
    )
    empresas_disponiveis = models.ManyToManyField(
        Empresa,
        blank=True,
        related_name="cursos_disponiveis",
        verbose_name="empresas com acesso",
    )
    validade_meses = models.PositiveIntegerField(default=6)
    nota_minima = models.PositiveSmallIntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    link_notebooklm = models.URLField(blank=True, null=True)
    ativo = models.BooleanField(default=True)
    data_criacao = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.nome


class EtapaCurso(models.Model):
    class Tipo(models.TextChoices):
        TEXTO = "texto", "Conteúdo em texto"
        VIDEO = "video", "Vídeo"
        TESTE = "teste", "Teste"
        PROVA = "prova", "Prova final"

    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name="etapas")
    titulo = models.CharField(max_length=180)
    descricao = models.TextField(blank=True)
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    ordem = models.PositiveIntegerField()
    conteudo = models.TextField(blank=True)
    video_url = models.URLField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ("ordem", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("curso", "ordem"), name="etapa_ordem_unica_por_curso"
            )
        ]

    @property
    def avaliativa(self):
        return self.tipo in {self.Tipo.TESTE, self.Tipo.PROVA}

    def __str__(self):
        return f"{self.curso} - {self.ordem}. {self.titulo}"


class Questao(models.Model):
    etapa = models.ForeignKey(
        EtapaCurso, on_delete=models.CASCADE, related_name="questoes"
    )
    enunciado = models.TextField()
    ordem = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("ordem", "id")

    def __str__(self):
        return self.enunciado[:80]


class Alternativa(models.Model):
    questao = models.ForeignKey(
        Questao, on_delete=models.CASCADE, related_name="alternativas"
    )
    texto = models.CharField(max_length=500)
    correta = models.BooleanField(default=False)
    ordem = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ("ordem", "id")

    def __str__(self):
        return self.texto


class CursoLiberado(models.Model):
    tecnico = models.ForeignKey(
        Tecnico, on_delete=models.PROTECT, related_name="cursos_liberados"
    )
    curso = models.ForeignKey(
        Curso, on_delete=models.PROTECT, related_name="liberacoes"
    )
    data_liberacao = models.DateField(default=timezone.now)
    obrigatorio = models.BooleanField(default=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Curso liberado"
        verbose_name_plural = "Cursos liberados"
        unique_together = ("tecnico", "curso")

    def __str__(self):
        return f"{self.tecnico} - {self.curso}"


class ProgressoCurso(models.Model):
    class Status(models.TextChoices):
        NAO_INICIADO = "nao_iniciado", "Não iniciado"
        EM_ANDAMENTO = "em_andamento", "Em andamento"
        APROVADO = "aprovado", "Aprovado"
        REPROVADO = "reprovado", "Reprovado"

    tecnico = models.ForeignKey(
        Tecnico, on_delete=models.CASCADE, related_name="progressos"
    )
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name="progressos")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NAO_INICIADO
    )
    tentativa_atual = models.PositiveIntegerField(default=1)
    iniciado_em = models.DateTimeField(blank=True, null=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tecnico", "curso"), name="progresso_unico_por_tecnico_curso"
            )
        ]

    def __str__(self):
        return f"{self.tecnico} - {self.curso} ({self.get_status_display()})"


class ProgressoEtapa(models.Model):
    progresso = models.ForeignKey(
        ProgressoCurso, on_delete=models.CASCADE, related_name="etapas_concluidas"
    )
    etapa = models.ForeignKey(
        EtapaCurso, on_delete=models.CASCADE, related_name="progressos"
    )
    tentativa = models.PositiveIntegerField(default=1)
    concluida_em = models.DateTimeField(default=timezone.now)
    nota = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("progresso", "etapa", "tentativa"),
                name="conclusao_etapa_unica_por_tentativa",
            )
        ]

    def __str__(self):
        return f"{self.progresso} - {self.etapa}"


class TentativaAvaliacao(models.Model):
    progresso = models.ForeignKey(
        ProgressoCurso, on_delete=models.CASCADE, related_name="avaliacoes"
    )
    etapa = models.ForeignKey(
        EtapaCurso, on_delete=models.CASCADE, related_name="tentativas"
    )
    numero_tentativa_curso = models.PositiveIntegerField()
    nota = models.DecimalField(max_digits=5, decimal_places=2)
    aprovado = models.BooleanField(default=False)
    realizada_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-realizada_em",)

    def __str__(self):
        return f"{self.progresso} - {self.etapa} ({self.nota}%)"


class ConclusaoTreinamento(models.Model):
    tecnico = models.ForeignKey(
        Tecnico, on_delete=models.PROTECT, related_name="conclusoes"
    )
    curso = models.ForeignKey(
        Curso, on_delete=models.PROTECT, related_name="conclusoes"
    )
    codigo_certificado = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        editable=False,
    )
    data_conclusao = models.DateField(default=timezone.now)
    data_vencimento = models.DateField(blank=True, null=True)
    observacao = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.codigo_certificado:
            self.codigo_certificado = self._gerar_codigo_certificado()

        if self.data_conclusao and not self.data_vencimento:
            self.data_vencimento = self.data_conclusao + relativedelta(
                months=self.curso.validade_meses
            )

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tecnico} - {self.curso}"

    @classmethod
    def _gerar_codigo_certificado(cls):
        while True:
            codigo = f"CERT-{secrets.token_hex(4).upper()}"
            if not cls.objects.filter(codigo_certificado=codigo).exists():
                return codigo
