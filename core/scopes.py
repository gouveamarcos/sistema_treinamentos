from .models import Empresa


def empresas_do_usuario(user):
    if not getattr(user, "is_authenticated", False):
        return Empresa.objects.none()

    if user.is_superuser:
        return Empresa.objects.filter(ativa=True)

    return Empresa.objects.filter(
        ativa=True,
        responsaveis__usuario=user,
        responsaveis__ativo=True,
    ).distinct()


def usuario_tem_escopo_total(user):
    return bool(getattr(user, "is_superuser", False))


def usuario_pode_gerenciar_catalogo(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True

    from .models import ResponsavelEmpresa

    return ResponsavelEmpresa.objects.filter(
        usuario=user,
        papel=ResponsavelEmpresa.Papel.EDITOR_CURSOS,
        ativo=True,
    ).exists()


def usuario_pode_operar_empresas(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True

    from .models import ResponsavelEmpresa

    return ResponsavelEmpresa.objects.filter(
        usuario=user,
        papel=ResponsavelEmpresa.Papel.OPERACIONAL,
        ativo=True,
    ).exists()


def papeis_responsavel_usuario(user):
    if not getattr(user, "is_authenticated", False):
        return set()
    if user.is_superuser:
        return {"superadmin"}

    from .models import ResponsavelEmpresa

    return set(
        ResponsavelEmpresa.objects.filter(usuario=user, ativo=True).values_list(
            "papel",
            flat=True,
        )
    )
