from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


GRUPO_RESPONSAVEL_OPERACIONAL = "Responsável operacional"
GRUPO_EDITOR_CURSOS = "Editor de cursos"

GRUPOS_INICIAIS = {
    GRUPO_RESPONSAVEL_OPERACIONAL: [
        "empresa",
        "tecnico",
        "cursoliberado",
        "progressocurso",
        "progressoetapa",
        "tentativaavaliacao",
        "conclusaotreinamento",
    ],
    GRUPO_EDITOR_CURSOS: [
        "produto",
        "curso",
        "etapacurso",
        "questao",
        "alternativa",
    ],
}

ACOES_PERMITIDAS = ("view", "add", "change")


def garantir_grupos_iniciais(sender=None, **kwargs):
    if sender is not None and sender.label != "core":
        return

    for nome_grupo, modelos in GRUPOS_INICIAIS.items():
        grupo, _ = Group.objects.get_or_create(name=nome_grupo)
        permissoes = []
        for modelo in modelos:
            content_type = ContentType.objects.filter(
                app_label="core",
                model=modelo,
            ).first()
            if not content_type:
                continue

            codenames = [f"{acao}_{modelo}" for acao in ACOES_PERMITIDAS]
            permissoes.extend(
                Permission.objects.filter(
                    content_type=content_type,
                    codename__in=codenames,
                )
            )

        grupo.permissions.set(permissoes)
