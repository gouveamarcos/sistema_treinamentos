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
