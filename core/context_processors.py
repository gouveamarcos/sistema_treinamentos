from .scopes import (
    empresas_do_usuario,
    usuario_pode_gerenciar_catalogo,
    usuario_pode_operar_empresas,
)

EMPRESA_CONTEXTO_SESSION_KEY = "empresa_operacional_id"


def permissoes_operacionais(request):
    user = request.user
    if not getattr(user, "is_authenticated", False):
        return {
            "pode_operar_empresas": False,
            "pode_gerenciar_catalogo": False,
            "empresas_do_menu": [],
        }

    empresas = empresas_do_usuario(user)
    empresa_contexto = None
    empresa_id = request.session.get(EMPRESA_CONTEXTO_SESSION_KEY)
    if empresa_id:
        empresa_contexto = empresas.filter(pk=empresa_id, ativa=True).first()
    return {
        "pode_operar_empresas": usuario_pode_operar_empresas(user),
        "pode_gerenciar_catalogo": usuario_pode_gerenciar_catalogo(user),
        "empresas_do_menu": empresas,
        "empresa_contexto": empresa_contexto,
    }
