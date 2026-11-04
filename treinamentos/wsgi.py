"""
WSGI config for treinamentos project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'treinamentos.settings')

application = get_wsgi_application()

# Avisos de reciclagem automaticos enquanto o site estiver ligado.
# Para desligar, defina AVISOS_RECICLAGEM_AUTOMATICOS=False no .env.
if os.getenv("AVISOS_RECICLAGEM_AUTOMATICOS", "True").strip().lower() not in {
    "0", "false", "no", "nao", "off",
}:
    from core.agendador import iniciar_agendador

    iniciar_agendador()
