from django.core.management.base import BaseCommand

from core.reciclagem import DIAS_DE_ANTECEDENCIA, enviar_avisos_reciclagem


class Command(BaseCommand):
    help = (
        "Envia agora os avisos de reciclagem que faltam. Com o site ligado, "
        "isso ja acontece sozinho de hora em hora."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias",
            type=int,
            default=DIAS_DE_ANTECEDENCIA,
            help=f"Dias de antecedencia do primeiro aviso (padrao: {DIAS_DE_ANTECEDENCIA}).",
        )

    def handle(self, *args, **options):
        enviados, falhas = enviar_avisos_reciclagem(antecedencia=options["dias"])
        self.stdout.write(self.style.SUCCESS(f"{enviados} lembrete(s) enviado(s)."))
        if falhas:
            self.stdout.write(self.style.ERROR(f"{falhas} lembrete(s) falharam."))
