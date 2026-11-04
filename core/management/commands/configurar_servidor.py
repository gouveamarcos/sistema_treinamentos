import getpass
import shutil
import socket
from urllib.parse import urlparse

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.core.management.base import BaseCommand, CommandError
from django.core.management.utils import get_random_secret_key

SITE_PADRAO = "https://monitoramento.viafacil.com.br/treinamento"
SMTP_PADRAO = "smtp.office365.com"
SITE_TESTE = "http://localhost:8000"


def ler_env(arquivo):
    valores = {}
    if not arquivo.exists():
        return valores
    for linha in arquivo.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        nome, valor = linha.split("=", 1)
        valores[nome.strip()] = valor.strip().strip('"').strip("'")
    return valores


def site_valido(site):
    endereco = urlparse(site)
    return (
        " " not in site
        and endereco.scheme in {"http", "https"}
        and bool(endereco.hostname)
    )


def nomes_deste_computador():
    nomes = {"localhost", "127.0.0.1"}
    try:
        nome = socket.gethostname()
        nomes.add(nome)
        nomes.update(socket.gethostbyname_ex(nome)[2])
    except OSError:
        pass
    return nomes


def montar_configuracao(atual, site, email, senha, smtp, porta):
    endereco = urlparse(site)
    if endereco.scheme not in {"http", "https"} or not endereco.hostname:
        raise CommandError(
            "Endereco do site invalido. Exemplo: " + SITE_PADRAO
        )
    https = endereco.scheme == "https"
    origem = f"{endereco.scheme}://{endereco.netloc}"
    hosts = sorted(nomes_deste_computador() | {endereco.hostname})

    valores = dict(atual)
    valores.update(
        {
            "DJANGO_DEBUG": "False",
            "DJANGO_SECRET_KEY": atual.get("DJANGO_SECRET_KEY")
            or get_random_secret_key(),
            "DJANGO_SITE_URL": site,
            "DJANGO_URL_PREFIX": endereco.path.strip("/"),
            "DJANGO_ALLOWED_HOSTS": ",".join(hosts),
            "DJANGO_CSRF_TRUSTED_ORIGINS": origem,
            # O HTTPS fica a cargo do proxy; o runserver so fala HTTP.
            "SECURE_SSL_REDIRECT": "False",
            "SESSION_COOKIE_SECURE": str(https),
            "CSRF_COOKIE_SECURE": str(https),
            "SECURE_HSTS_SECONDS": "0",
            "SECURE_HSTS_INCLUDE_SUBDOMAINS": "False",
            "SECURE_HSTS_PRELOAD": "False",
            "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "EMAIL_HOST": smtp,
            "EMAIL_PORT": str(porta),
            "EMAIL_HOST_USER": email,
            "EMAIL_HOST_PASSWORD": senha,
            "EMAIL_USE_TLS": str(porta != 465),
            "EMAIL_USE_SSL": str(porta == 465),
            # O Outlook so aceita enviar com o proprio e-mail como remetente.
            "DEFAULT_FROM_EMAIL": f"Academia Tecnica <{email}>",
        }
    )
    return valores


def escrever_env(arquivo, valores):
    linhas = [
        "# Criado por: python manage.py configurar_servidor",
        "# Para mudar algo, rode o comando de novo ou edite com cuidado.",
    ]
    linhas += [f"{nome}={valor}" for nome, valor in valores.items()]
    arquivo.write_text("\n".join(linhas) + "\n", encoding="utf-8")


class Command(BaseCommand):
    help = "Cria o arquivo .env do servidor fazendo perguntas simples."

    def perguntar(self, texto, padrao=""):
        sufixo = f" [{padrao}]" if padrao else ""
        resposta = input(f"{texto}{sufixo}: ").strip()
        return resposta or padrao

    def perguntar_site(self, padrao):
        if site_valido(padrao):
            resposta = self.perguntar(
                f"O endereco do site e {padrao} ? (S/N)", "S"
            )
            if resposta.lower().startswith("s"):
                return padrao
        while True:
            site = self.perguntar(
                "Qual e o endereco do site? Para testar neste computador, "
                "so aperte Enter",
                SITE_TESTE,
            ).rstrip("/")
            if site_valido(site):
                return site
            self.stdout.write(
                self.style.ERROR(
                    "Endereco invalido. Digite so o endereco, por exemplo "
                    f"{SITE_TESTE}"
                )
            )

    def handle(self, *args, **options):
        arquivo = settings.BASE_DIR / ".env"
        atual = ler_env(arquivo)

        self.stdout.write("")
        self.stdout.write("Configuracao da Academia Tecnica")
        self.stdout.write("Aperte Enter para aceitar o valor entre colchetes.")
        self.stdout.write("")

        site = self.perguntar_site(atual.get("DJANGO_SITE_URL") or SITE_PADRAO)
        email = self.perguntar(
            "E-mail do Outlook que envia as mensagens",
            atual.get("EMAIL_HOST_USER", ""),
        )
        if not email or "@" not in email:
            raise CommandError("Informe o e-mail que envia as mensagens.")
        senha = getpass.getpass(
            "Senha desse e-mail (nao aparece enquanto digita; Enter mantem a atual): "
        ) or atual.get("EMAIL_HOST_PASSWORD", "")
        if not senha:
            raise CommandError("Informe a senha do e-mail.")
        smtp = self.perguntar(
            "Servidor de e-mail", atual.get("EMAIL_HOST") or SMTP_PADRAO
        )
        try:
            porta = int(self.perguntar("Porta", atual.get("EMAIL_PORT") or "587"))
        except ValueError:
            raise CommandError("A porta deve ser um numero, por exemplo 587.")

        valores = montar_configuracao(atual, site, email, senha, smtp, porta)

        if arquivo.exists():
            shutil.copyfile(arquivo, settings.BASE_DIR / ".env.anterior")
            self.stdout.write("Copia do .env antigo salva em .env.anterior")
        escrever_env(arquivo, valores)
        self.stdout.write(self.style.SUCCESS(f"Configuracao salva em {arquivo}"))

        banco = settings.DATABASES["default"]["NAME"]
        if "sqlite3" in settings.DATABASES["default"]["ENGINE"] and not (
            settings.BASE_DIR / banco
        ).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"ATENCAO: o banco de dados nao foi encontrado em {banco}. "
                    "Copie o db.sqlite3 de volta para esta pasta antes de ligar."
                )
            )

        destino = self.perguntar(
            "Para testar, digite um e-mail que deve receber uma mensagem "
            "(ou Enter para pular)"
        )
        if destino:
            self.enviar_teste(valores, destino)

    def enviar_teste(self, valores, destino):
        conexao = get_connection(
            backend=valores["EMAIL_BACKEND"],
            host=valores["EMAIL_HOST"],
            port=int(valores["EMAIL_PORT"]),
            username=valores["EMAIL_HOST_USER"],
            password=valores["EMAIL_HOST_PASSWORD"],
            use_tls=valores["EMAIL_USE_TLS"] == "True",
            use_ssl=valores["EMAIL_USE_SSL"] == "True",
            timeout=20,
        )
        try:
            EmailMessage(
                "Teste da Academia Tecnica",
                "Se esta mensagem chegou, o envio de e-mails esta funcionando.\n\n"
                f"Endereco do site: {valores['DJANGO_SITE_URL']}/",
                valores["DEFAULT_FROM_EMAIL"],
                [destino],
                connection=conexao,
            ).send()
        except Exception as erro:
            self.stdout.write(
                self.style.ERROR(f"O e-mail de teste NAO foi enviado: {erro}")
            )
            return
        self.stdout.write(
            self.style.SUCCESS(f"E-mail de teste enviado para {destino}.")
        )
