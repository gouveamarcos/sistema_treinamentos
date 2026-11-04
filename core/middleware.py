from django.conf import settings


class PrefixoUrlMiddleware:
    # Alguns proxies repassam /treinamento/login/ e outros so /login/.
    # Aqui os dois casos viram /login/ para o sistema encontrar a pagina.
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        prefixo = settings.FORCE_SCRIPT_NAME
        if prefixo:
            caminho = request.path_info
            if caminho == prefixo or caminho.startswith(f"{prefixo}/"):
                request.path_info = caminho[len(prefixo):] or "/"
                request.path = f"{prefixo}{request.path_info}"
        return self.get_response(request)
