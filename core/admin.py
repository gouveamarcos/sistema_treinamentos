from datetime import timedelta

from django.contrib import admin
from django.utils import timezone

from .models import (
    Alternativa,
    ConclusaoTreinamento,
    Curso,
    CursoLiberado,
    Empresa,
    EtapaCurso,
    EventoAuditoria,
    Produto,
    ProgressoCurso,
    ProgressoEtapa,
    Questao,
    ResponsavelEmpresa,
    Tecnico,
    TentativaAvaliacao,
)
from .scopes import empresas_do_usuario, usuario_tem_escopo_total


def _empresas_visiveis(request):
    return empresas_do_usuario(request.user)


def _filtrar_por_empresa(request, queryset, lookup):
    if usuario_tem_escopo_total(request.user):
        return queryset
    return queryset.filter(**{f"{lookup}__in": _empresas_visiveis(request)})


class SituacaoVencimentoFilter(admin.SimpleListFilter):
    title = "situação do vencimento"
    parameter_name = "situacao_vencimento"

    def lookups(self, request, model_admin):
        return (
            ("vencido", "Vencido"),
            ("proximos_30", "Vence em até 30 dias"),
            ("em_dia", "Em dia"),
            ("sem_vencimento", "Sem vencimento"),
        )

    def queryset(self, request, queryset):
        hoje = timezone.localdate()
        limite = hoje + timedelta(days=30)

        if self.value() == "vencido":
            return queryset.filter(data_vencimento__lt=hoje)
        if self.value() == "proximos_30":
            return queryset.filter(
                data_vencimento__gte=hoje,
                data_vencimento__lte=limite,
            )
        if self.value() == "em_dia":
            return queryset.filter(data_vencimento__gt=limite)
        if self.value() == "sem_vencimento":
            return queryset.filter(data_vencimento__isnull=True)
        return queryset


class EtapaCursoInline(admin.TabularInline):
    model = EtapaCurso
    extra = 0
    fields = ("ordem", "titulo", "tipo", "ativo")
    show_change_link = True


class AlternativaInline(admin.TabularInline):
    model = Alternativa
    extra = 4


@admin.register(EventoAuditoria)
class EventoAuditoriaAdmin(admin.ModelAdmin):
    list_display = (
        "criado_em",
        "usuario",
        "empresa",
        "acao",
        "alvo_tipo",
        "alvo_repr",
    )
    list_filter = ("acao", "empresa", "alvo_tipo", "criado_em")
    search_fields = (
        "usuario__username",
        "usuario__email",
        "empresa__nome",
        "alvo_repr",
        "detalhes",
    )
    readonly_fields = (
        "usuario",
        "empresa",
        "acao",
        "alvo_tipo",
        "alvo_id",
        "alvo_repr",
        "detalhes",
        "criado_em",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return _filtrar_por_empresa(request, queryset, "empresa")


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nome", "documento", "responsavel", "email", "ativa")
    search_fields = ("nome", "documento", "responsavel", "email")
    list_filter = ("ativa",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if usuario_tem_escopo_total(request.user):
            return queryset
        return queryset.filter(pk__in=_empresas_visiveis(request))


@admin.register(ResponsavelEmpresa)
class ResponsavelEmpresaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "empresa", "papel", "ativo", "data_criacao")
    search_fields = (
        "usuario__username",
        "usuario__email",
        "empresa__nome",
    )
    list_filter = ("empresa", "papel", "ativo")
    autocomplete_fields = ("usuario", "empresa")
    readonly_fields = ("data_criacao",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return _filtrar_por_empresa(request, queryset, "empresa")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "empresa" and not usuario_tem_escopo_total(request.user):
            kwargs["queryset"] = _empresas_visiveis(request)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Produto)
class ProdutoAdmin(admin.ModelAdmin):
    list_display = ("nome", "ativo")
    search_fields = ("nome",)
    list_filter = ("ativo",)


@admin.register(Tecnico)
class TecnicoAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "empresa",
        "email",
        "matricula",
        "equipe",
        "regiao",
        "ativo",
    )
    search_fields = ("nome", "email", "matricula", "empresa__nome")
    list_filter = ("empresa", "equipe", "regiao", "ativo")
    autocomplete_fields = ("usuario",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return _filtrar_por_empresa(request, queryset, "empresa")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "empresa" and not usuario_tem_escopo_total(request.user):
            kwargs["queryset"] = _empresas_visiveis(request)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("nome", "produto", "nota_minima", "validade_meses", "ativo")
    search_fields = ("nome", "produto__nome", "empresas_disponiveis__nome")
    list_filter = ("produto", "empresas_disponiveis", "ativo")
    filter_horizontal = ("empresas_disponiveis",)
    inlines = (EtapaCursoInline,)


@admin.register(EtapaCurso)
class EtapaCursoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "curso", "ordem", "tipo", "ativo")
    list_filter = ("curso__produto", "curso", "tipo", "ativo")
    search_fields = ("titulo", "curso__nome")


@admin.register(Questao)
class QuestaoAdmin(admin.ModelAdmin):
    list_display = ("enunciado_resumido", "etapa", "ordem")
    list_filter = ("etapa__curso",)
    search_fields = ("enunciado", "etapa__titulo")
    inlines = (AlternativaInline,)

    @admin.display(description="Questão")
    def enunciado_resumido(self, obj):
        return str(obj)


@admin.register(CursoLiberado)
class CursoLiberadoAdmin(admin.ModelAdmin):
    list_display = ("tecnico", "curso", "data_liberacao", "obrigatorio", "ativo")
    search_fields = (
        "tecnico__nome",
        "tecnico__email",
        "tecnico__empresa__nome",
        "curso__nome",
    )
    list_filter = ("tecnico__empresa", "curso__produto", "obrigatorio", "ativo")
    autocomplete_fields = ("tecnico", "curso")
    actions = (
        "marcar_como_ativas",
        "marcar_como_inativas",
        "marcar_como_obrigatorias",
        "marcar_como_opcionais",
    )

    @admin.action(description="Marcar liberações selecionadas como ativas")
    def marcar_como_ativas(self, request, queryset):
        queryset.update(ativo=True)

    @admin.action(description="Marcar liberações selecionadas como inativas")
    def marcar_como_inativas(self, request, queryset):
        queryset.update(ativo=False)

    @admin.action(description="Marcar liberações selecionadas como obrigatórias")
    def marcar_como_obrigatorias(self, request, queryset):
        queryset.update(obrigatorio=True)

    @admin.action(description="Marcar liberações selecionadas como opcionais")
    def marcar_como_opcionais(self, request, queryset):
        queryset.update(obrigatorio=False)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return _filtrar_por_empresa(request, queryset, "tecnico__empresa")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "tecnico" and not usuario_tem_escopo_total(request.user):
            kwargs["queryset"] = Tecnico.objects.filter(
                ativo=True,
                empresa__in=_empresas_visiveis(request),
            ).order_by("empresa__nome", "nome")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ProgressoCurso)
class ProgressoCursoAdmin(admin.ModelAdmin):
    list_display = ("tecnico", "curso", "status", "tentativa_atual", "atualizado_em")
    list_filter = ("tecnico__empresa", "status", "curso__produto", "curso")
    search_fields = (
        "tecnico__nome",
        "tecnico__matricula",
        "tecnico__empresa__nome",
        "curso__nome",
    )
    readonly_fields = ("atualizado_em",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return _filtrar_por_empresa(request, queryset, "tecnico__empresa")


@admin.register(ProgressoEtapa)
class ProgressoEtapaAdmin(admin.ModelAdmin):
    list_display = ("progresso", "etapa", "tentativa", "nota", "concluida_em")
    list_filter = ("etapa__curso", "tentativa")
    readonly_fields = ("concluida_em",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return _filtrar_por_empresa(request, queryset, "progresso__tecnico__empresa")


@admin.register(TentativaAvaliacao)
class TentativaAvaliacaoAdmin(admin.ModelAdmin):
    list_display = (
        "progresso",
        "etapa",
        "numero_tentativa_curso",
        "nota",
        "aprovado",
        "realizada_em",
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return _filtrar_por_empresa(request, queryset, "progresso__tecnico__empresa")
    list_filter = ("aprovado", "etapa__curso")
    readonly_fields = (
        "progresso",
        "etapa",
        "numero_tentativa_curso",
        "nota",
        "aprovado",
        "realizada_em",
    )


@admin.register(ConclusaoTreinamento)
class ConclusaoTreinamentoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo_certificado",
        "tecnico",
        "curso",
        "data_conclusao",
        "data_vencimento",
        "situacao_vencimento",
        "dias_para_vencer",
    )
    search_fields = (
        "codigo_certificado",
        "tecnico__nome",
        "tecnico__empresa__nome",
        "curso__nome",
    )
    list_filter = (
        "tecnico__empresa",
        SituacaoVencimentoFilter,
        "curso",
        "data_conclusao",
        "data_vencimento",
    )
    readonly_fields = ("codigo_certificado",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return _filtrar_por_empresa(request, queryset, "tecnico__empresa")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "tecnico" and not usuario_tem_escopo_total(request.user):
            kwargs["queryset"] = Tecnico.objects.filter(
                ativo=True,
                empresa__in=_empresas_visiveis(request),
            ).order_by("empresa__nome", "nome")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="Situação")
    def situacao_vencimento(self, obj):
        if not obj.data_vencimento:
            return "Sem vencimento"

        hoje = timezone.localdate()
        if obj.data_vencimento < hoje:
            return "Vencido"
        if obj.data_vencimento <= hoje + timedelta(days=30):
            return "Vence em até 30 dias"
        return "Em dia"

    @admin.display(description="Dias para vencer", ordering="data_vencimento")
    def dias_para_vencer(self, obj):
        if not obj.data_vencimento:
            return "-"

        return (obj.data_vencimento - timezone.localdate()).days


admin.site.site_header = "Academia Técnica Sem Parar"
admin.site.site_title = "Gestão de treinamentos"
admin.site.index_title = "Administração da plataforma"
