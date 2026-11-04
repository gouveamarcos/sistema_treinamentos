from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOuUsuarioBackend(ModelBackend):
    # A tela de login pede o e-mail, mas contas como a do superadmin tem um
    # nome de usuario diferente (ex.: admin). Aceita os dois.
    def authenticate(self, request, username=None, password=None, **kwargs):
        usuario = super().authenticate(
            request, username=username, password=password, **kwargs
        )
        if usuario is not None or not username or password is None:
            return usuario
        if "@" not in username:
            return None
        contas = get_user_model()._default_manager.filter(email__iexact=username)
        for conta in contas:
            if conta.check_password(password) and self.user_can_authenticate(conta):
                return conta
        return None
