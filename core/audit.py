from .models import EventoAuditoria


def registrar_evento(
    usuario,
    acao,
    alvo,
    *,
    empresa=None,
    detalhes="",
):
    if empresa is None:
        empresa = getattr(alvo, "empresa", None)

    return EventoAuditoria.objects.create(
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        empresa=empresa,
        acao=acao,
        alvo_tipo=alvo.__class__.__name__,
        alvo_id=getattr(alvo, "pk", None),
        alvo_repr=str(alvo)[:255],
        detalhes=detalhes,
    )
