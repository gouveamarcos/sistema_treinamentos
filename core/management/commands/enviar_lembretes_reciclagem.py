from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from core.models import ConclusaoTreinamento, CursoLiberado


class Command(BaseCommand):
    help = "Envia avisos de cursos vencidos ou que vencem nos próximos dias."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias",
            type=int,
            default=30,
            help="Janela de dias antes do vencimento (padrão: 30).",
        )

    def handle(self, *args, **options):
        hoje = timezone.localdate()
        limite = hoje + timedelta(days=options["dias"])
        ultima_conclusao = ConclusaoTreinamento.objects.filter(
            tecnico=OuterRef("tecnico"), curso=OuterRef("curso")
        ).order_by("-data_conclusao")

        liberacoes = (
            CursoLiberado.objects.filter(
                ativo=True, tecnico__ativo=True, curso__ativo=True
            )
            .annotate(
                vencimento=Subquery(ultima_conclusao.values("data_vencimento")[:1])
            )
            .filter(vencimento__lte=limite)
            .select_related("tecnico", "curso")
        )

        enviados = 0
        for liberacao in liberacoes:
            situacao = (
                "está vencido"
                if liberacao.vencimento < hoje
                else f"vence em {liberacao.vencimento:%d/%m/%Y}"
            )
            send_mail(
                subject=f"Reciclagem necessária: {liberacao.curso.nome}",
                message=(
                    f"Olá, {liberacao.tecnico.nome}.\n\n"
                    f"Seu treinamento {liberacao.curso.nome} {situacao}. "
                    "Acesse a Academia Técnica para realizar a reciclagem.\n\n"
                    "Academia Técnica Sem Parar"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[liberacao.tecnico.email],
            )
            enviados += 1

        self.stdout.write(self.style.SUCCESS(f"{enviados} lembrete(s) enviado(s)."))
