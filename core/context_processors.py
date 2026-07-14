from .scopes import (
    empresas_do_usuario,
    usuario_pode_gerenciar_catalogo,
    usuario_pode_operar_empresas,
)


def permissoes_operacionais(request):
    user = request.user
    if not getattr(user, "is_authenticated", False):
        return {
            "pode_operar_empresas": False,
            "pode_gerenciar_catalogo": False,
            "empresas_do_menu": [],
        }

    empresas = empresas_do_usuario(user)
    return {
        "pode_operar_empresas": usuario_pode_operar_empresas(user),
        "pode_gerenciar_catalogo": usuario_pode_gerenciar_catalogo(user),
        "empresas_do_menu": empresas,
    }
