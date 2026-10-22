import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Cria ou redefine um usuario administrador."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="admin",
            help="Nome de usuario do administrador. Padrao: admin.",
        )
        parser.add_argument(
            "--email",
            default="",
            help="E-mail do administrador.",
        )
        parser.add_argument(
            "--password",
            default=None,
            help="Senha nova. Use preferencialmente apenas em automacoes seguras.",
        )
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Nao solicitar dados interativamente.",
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        email = options["email"].strip()
        password = options["password"]

        if not username:
            raise CommandError("Informe um username valido.")

        if password is None and not options["noinput"]:
            password = self._solicitar_senha()

        if not password:
            raise CommandError(
                "Informe a senha com --password ou execute sem --noinput para digitar."
            )

        User = get_user_model()
        usuario = User.objects.filter(username=username).first()
        criado = usuario is None
        if criado:
            usuario = User(username=username, email=email)

        # Valida a senha antes de gravar qualquer coisa: se ela for recusada,
        # nenhum usuario e criado ou alterado.
        try:
            validate_password(password, usuario)
        except ValidationError as erro:
            raise CommandError(" ".join(erro.messages)) from erro

        usuario.set_password(password)
        usuario.is_staff = True
        usuario.is_superuser = True
        usuario.is_active = True
        if email:
            usuario.email = email
        usuario.save()

        acao = "criado" if criado else "redefinido"
        self.stdout.write(
            self.style.SUCCESS(
                f"Administrador '{usuario.username}' {acao} com sucesso."
            )
        )

    def _solicitar_senha(self):
        senha = getpass.getpass("Nova senha do administrador: ")
        confirmacao = getpass.getpass("Confirme a nova senha: ")

        if senha != confirmacao:
            raise CommandError("As senhas nao conferem.")

        return senha
