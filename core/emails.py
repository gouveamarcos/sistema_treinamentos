from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import get_script_prefix, reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def link_absoluto(request, caminho):
    # Atras de um proxy o servidor nao enxerga o endereco publico do site.
    # Com DJANGO_SITE_URL definido, os links dos e-mails usam esse endereco.
    if settings.SITE_URL:
        prefixo = get_script_prefix()
        if caminho.startswith(prefixo):
            caminho = caminho[len(prefixo):]
        return f"{settings.SITE_URL}/{caminho.lstrip('/')}"
    return request.build_absolute_uri(caminho)


def link_definir_senha(request, uid, token):
    caminho = reverse(
        "password_reset_confirm",
        kwargs={"uidb64": uid, "token": token},
    )
    return link_absoluto(request, caminho)


def _link_definir_senha(request, usuario):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    link = link_definir_senha(request, uid, token)
    endereco = urlparse(link)
    return endereco.scheme, endereco.netloc, link


def enviar_convite_responsavel(request, usuario, responsabilidade):
    protocolo, dominio, link = _link_definir_senha(request, usuario)
    contexto = {
        "usuario": usuario,
        "responsabilidade": responsabilidade,
        "empresa": responsabilidade.empresa,
        "protocolo": protocolo,
        "dominio": dominio,
        "link_acesso": link,
    }
    assunto = render_to_string(
        "core/emails/responsavel_invite_subject.txt",
        contexto,
    ).strip()
    mensagem = render_to_string(
        "core/emails/responsavel_invite_email.txt",
        contexto,
    )
    send_mail(assunto, mensagem, None, [usuario.email])


def enviar_convite_tecnico(request, usuario, tecnico):
    protocolo, dominio, link = _link_definir_senha(request, usuario)
    contexto = {
        "usuario": usuario,
        "tecnico": tecnico,
        "protocolo": protocolo,
        "dominio": dominio,
        "link_acesso": link,
    }
    assunto = render_to_string(
        "core/emails/tecnico_primeiro_acesso_subject.txt",
        contexto,
    ).strip()
    mensagem = render_to_string(
        "core/emails/tecnico_primeiro_acesso_email.txt",
        contexto,
    )
    send_mail(assunto, mensagem, None, [usuario.email])
