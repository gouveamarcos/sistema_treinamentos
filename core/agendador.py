import logging
import threading
import time

from django.db import close_old_connections

from .reciclagem import enviar_avisos_reciclagem

logger = logging.getLogger(__name__)

_iniciado = False


def _rodar_sempre(intervalo):
    time.sleep(30)
    while True:
        try:
            enviados, falhas = enviar_avisos_reciclagem()
            if enviados or falhas:
                logger.warning(
                    "Avisos de reciclagem: %s enviado(s), %s falha(s).",
                    enviados,
                    falhas,
                )
        except Exception:
            logger.exception("Erro ao verificar avisos de reciclagem")
        finally:
            close_old_connections()
        time.sleep(intervalo)


def iniciar_agendador(intervalo=60 * 60):
    # Enquanto o site estiver ligado, confere de hora em hora quem precisa
    # receber aviso de reciclagem. Cada aviso e enviado uma unica vez.
    global _iniciado
    if _iniciado:
        return
    _iniciado = True
    threading.Thread(
        target=_rodar_sempre,
        args=(intervalo,),
        daemon=True,
        name="avisos-reciclagem",
    ).start()
