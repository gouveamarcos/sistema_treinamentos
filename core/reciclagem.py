import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from .models import AvisoReciclagem, ConclusaoTreinamento, CursoLiberado

logger = logging.getLogger(__name__)

# Primeiro aviso: tantos dias antes de vencer. Segundo aviso: quando vence.
DIAS_DE_ANTECEDENCIA = 30


def _conclusoes_a_avisar(hoje, antecedencia):
    ultima_conclusao = ConclusaoTreinamento.objects.filter(
        tecnico=OuterRef("tecnico"), curso=OuterRef("curso")
    ).order_by("-data_conclusao", "-id")
    ids = (
        CursoLiberado.objects.filter(
            ativo=True, tecnico__ativo=True, curso__ativo=True
        )
        .annotate(conclusao_id=Subquery(ultima_conclusao.values("id")[:1]))
        .exclude(conclusao_id=None)
        .values_list("conclusao_id", flat=True)
    )
    return ConclusaoTreinamento.objects.filter(
        id__in=set(ids),
        data_vencimento__lte=hoje + timedelta(days=antecedencia),
    ).select_related("tecnico", "curso")


def _mensagem(conclusao, tipo):
    curso = conclusao.curso.nome
    vencimento = f"{conclusao.data_vencimento:%d/%m/%Y}"
    if tipo == AvisoReciclagem.Tipo.VENCIDO:
        assunto = f"Reciclagem necessária: {curso}"
        situacao = f"venceu em {vencimento}"
    else:
        assunto = f"Reciclagem em breve: {curso}"
        situacao = f"vence em {vencimento}"
    acesso = f" em {settings.SITE_URL}/" if settings.SITE_URL else ""
    corpo = (
        f"Olá, {conclusao.tecnico.nome}.\n\n"
        f"Seu treinamento {curso} {situacao}. "
        f"Acesse a Academia Técnica{acesso} para realizar a reciclagem.\n\n"
        f"Seu usuário de acesso é o seu e-mail: {conclusao.tecnico.email}\n\n"
        "Academia Técnica Sem Parar"
    )
    return assunto, corpo


def enviar_avisos_reciclagem(hoje=None, antecedencia=DIAS_DE_ANTECEDENCIA):
    """Envia os avisos que ainda faltam. Pode rodar varias vezes por dia."""
    hoje = hoje or timezone.localdate()
    enviados = falhas = 0
    for conclusao in _conclusoes_a_avisar(hoje, antecedencia):
        if conclusao.data_vencimento <= hoje:
            tipo = AvisoReciclagem.Tipo.VENCIDO
        else:
            tipo = AvisoReciclagem.Tipo.VENCENDO
        if AvisoReciclagem.objects.filter(conclusao=conclusao, tipo=tipo).exists():
            continue
        try:
            with transaction.atomic():
                aviso = AvisoReciclagem.objects.create(conclusao=conclusao, tipo=tipo)
        except IntegrityError:
            continue

        assunto, corpo = _mensagem(conclusao, tipo)
        try:
            send_mail(assunto, corpo, None, [conclusao.tecnico.email])
        except Exception:
            # Sem registro, o aviso e tentado de novo na proxima rodada.
            aviso.delete()
            logger.exception("Falha ao enviar aviso de reciclagem a %s", conclusao.tecnico.email)
            falhas += 1
            continue
        enviados += 1
    return enviados, falhas
