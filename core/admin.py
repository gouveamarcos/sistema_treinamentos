from django.contrib import admin

from .models import (
    Alternativa,
    ConclusaoTreinamento,
    Curso,
    CursoLiberado,
    Empresa,
    EtapaCurso,
    Produto,
    ProgressoCurso,
    ProgressoEtapa,
    Questao,
    Tecnico,
    TentativaAvaliacao,
)


class EtapaCursoInline(admin.TabularInline):
    model = EtapaCurso
    extra = 0
    fields = ("ordem", "titulo", "tipo", "ativo")
    show_change_link = True


class AlternativaInline(admin.TabularInline):
    model = Alternativa
    extra = 4


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nome", "documento", "responsavel", "email", "ativa")
    search_fields = ("nome", "documento", "responsavel", "email")
    list_filter = ("ativa",)


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


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("nome", "produto", "nota_minima", "validade_meses", "ativo")
    search_fields = ("nome", "produto__nome")
    list_filter = ("produto", "ativo")
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


@admin.register(ProgressoEtapa)
class ProgressoEtapaAdmin(admin.ModelAdmin):
    list_display = ("progresso", "etapa", "tentativa", "nota", "concluida_em")
    list_filter = ("etapa__curso", "tentativa")
    readonly_fields = ("concluida_em",)


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
    list_display = ("tecnico", "curso", "data_conclusao", "data_vencimento")
    search_fields = ("tecnico__nome", "tecnico__empresa__nome", "curso__nome")
    list_filter = ("tecnico__empresa", "curso", "data_conclusao", "data_vencimento")


admin.site.site_header = "Academia Técnica Sem Parar"
admin.site.site_title = "Gestão de treinamentos"
admin.site.index_title = "Administração da plataforma"
