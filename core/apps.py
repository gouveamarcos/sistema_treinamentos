from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        from django.db.models.signals import post_migrate

        from .permissions import garantir_grupos_iniciais

        post_migrate.connect(
            garantir_grupos_iniciais,
            sender=self,
            dispatch_uid="core.garantir_grupos_iniciais",
        )
