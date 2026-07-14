from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def enviar_convite_responsavel(request, usuario, responsabilidade):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    site = get_current_site(request)
    protocolo = "https" if request.is_secure() else "http"
    caminho = reverse(
        "password_reset_confirm",
        kwargs={"uidb64": uid, "token": token},
    )
    contexto = {
        "usuario": usuario,
        "responsabilidade": responsabilidade,
        "empresa": responsabilidade.empresa,
        "protocolo": protocolo,
        "dominio": site.domain,
        "link_acesso": f"{protocolo}://{site.domain}{caminho}",
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
