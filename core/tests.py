from datetime import timedelta
from io import StringIO
import re

from django.contrib.auth.models import User
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Alternativa,
    ConclusaoTreinamento,
    Curso,
    CursoLiberado,
    EtapaCurso,
    Produto,
    ProgressoCurso,
    ProgressoEtapa,
    Questao,
    Tecnico,
    TentativaAvaliacao,
)


class FluxoCursoTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="tecnico@exemplo.com", password="SenhaForte123!"
        )
        self.tecnico = Tecnico.objects.create(
            usuario=self.usuario,
            nome="Técnico Exemplo",
            email="tecnico@exemplo.com",
            matricula="TEC001",
        )
        self.produto = Produto.objects.create(nome="Abastece")
        self.curso = Curso.objects.create(
            nome="Manutenção básica",
            produto=self.produto,
            nota_minima=70,
        )
        CursoLiberado.objects.create(tecnico=self.tecnico, curso=self.curso)
        self.aula = EtapaCurso.objects.create(
            curso=self.curso,
            titulo="Introdução",
            tipo=EtapaCurso.Tipo.TEXTO,
            ordem=1,
            conteudo="Conteúdo introdutório.",
        )
        self.prova = EtapaCurso.objects.create(
            curso=self.curso,
            titulo="Prova final",
            tipo=EtapaCurso.Tipo.PROVA,
            ordem=2,
        )
        self.questao = Questao.objects.create(
            etapa=self.prova, enunciado="Qual é a resposta correta?"
        )
        self.correta = Alternativa.objects.create(
            questao=self.questao, texto="Correta", correta=True
        )
        self.errada = Alternativa.objects.create(
            questao=self.questao, texto="Errada", correta=False, ordem=2
        )
        self.client.force_login(self.usuario)

    def test_nao_permite_pular_etapa(self):
        resposta = self.client.get(
            reverse("curso_etapa", args=(self.curso.id, self.prova.id))
        )

        self.assertRedirects(
            resposta, reverse("curso_etapa", args=(self.curso.id, self.aula.id))
        )

    def test_reprovacao_reinicia_o_curso(self):
        self.client.post(reverse("curso_etapa", args=(self.curso.id, self.aula.id)))
        resposta = self.client.post(
            reverse("curso_etapa", args=(self.curso.id, self.prova.id)),
            {f"questao_{self.questao.id}": self.errada.id},
        )

        progresso = ProgressoCurso.objects.get(
            tecnico=self.tecnico, curso=self.curso
        )
        self.assertRedirects(
            resposta, reverse("curso_etapa", args=(self.curso.id, self.aula.id))
        )
        self.assertEqual(progresso.tentativa_atual, 2)
        self.assertFalse(
            ProgressoEtapa.objects.filter(
                progresso=progresso, tentativa=2
            ).exists()
        )
        self.assertTrue(
            TentativaAvaliacao.objects.filter(
                progresso=progresso, aprovado=False, nota=0
            ).exists()
        )

    def test_aprovacao_conclui_e_define_validade(self):
        self.client.post(reverse("curso_etapa", args=(self.curso.id, self.aula.id)))
        resposta = self.client.post(
            reverse("curso_etapa", args=(self.curso.id, self.prova.id)),
            {f"questao_{self.questao.id}": self.correta.id},
        )

        progresso = ProgressoCurso.objects.get(
            tecnico=self.tecnico, curso=self.curso
        )
        conclusao = ConclusaoTreinamento.objects.get(
            tecnico=self.tecnico, curso=self.curso
        )
        self.assertRedirects(
            resposta, reverse("cursos_por_produto", args=(self.produto.id,))
        )
        self.assertEqual(progresso.status, ProgressoCurso.Status.APROVADO)
        self.assertIsNotNone(conclusao.data_vencimento)
        self.assertTrue(
            TentativaAvaliacao.objects.filter(
                progresso=progresso, aprovado=True, nota=100
            ).exists()
        )

    def test_certificacao_vencida_abre_nova_tentativa(self):
        progresso = ProgressoCurso.objects.create(
            tecnico=self.tecnico,
            curso=self.curso,
            status=ProgressoCurso.Status.APROVADO,
            tentativa_atual=1,
            iniciado_em=timezone.now(),
        )
        ProgressoEtapa.objects.create(
            progresso=progresso, etapa=self.aula, tentativa=1
        )
        ProgressoEtapa.objects.create(
            progresso=progresso, etapa=self.prova, tentativa=1, nota=100
        )
        ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico,
            curso=self.curso,
            data_conclusao=timezone.localdate() - timedelta(days=190),
            data_vencimento=timezone.localdate() - timedelta(days=1),
        )

        resposta = self.client.get(reverse("curso_detalhe", args=(self.curso.id,)))

        progresso.refresh_from_db()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(progresso.tentativa_atual, 2)
        self.assertEqual(progresso.status, ProgressoCurso.Status.EM_ANDAMENTO)
        self.assertContains(resposta, self.aula.titulo)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="Academia Técnica <teste@exemplo.com>",
)
class RecuperacaoSenhaTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="tecnico@exemplo.com",
            email="tecnico@exemplo.com",
            password="SenhaAntiga123!",
            first_name="Técnico",
        )

    def test_fluxo_completo_de_recuperacao_de_senha(self):
        resposta = self.client.post(
            reverse("password_reset"), {"email": self.usuario.email}
        )

        self.assertRedirects(resposta, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.usuario.email, mail.outbox[0].to)
        caminho = re.search(
            r"/senha/redefinir/[^\s]+/[^\s]+/", mail.outbox[0].body
        ).group(0)

        resposta_link = self.client.get(caminho)
        self.assertEqual(resposta_link.status_code, 302)
        caminho_confirmacao = resposta_link.url

        resposta_senha = self.client.post(
            caminho_confirmacao,
            {
                "new_password1": "NovaSenhaSegura123!",
                "new_password2": "NovaSenhaSegura123!",
            },
        )

        self.assertRedirects(resposta_senha, reverse("password_reset_complete"))
        self.assertTrue(
            self.client.login(
                username=self.usuario.email, password="NovaSenhaSegura123!"
            )
        )

    def test_email_nao_cadastrado_nao_revela_existencia_de_conta(self):
        resposta = self.client.post(
            reverse("password_reset"), {"email": "inexistente@exemplo.com"}
        )

        self.assertRedirects(resposta, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)


class CargaDemonstracaoTest(TestCase):
    def test_cria_catalogo_sem_tecnico(self):
        saida = StringIO()

        call_command("criar_cursos_demonstracao", sem_tecnico=True, stdout=saida)

        self.assertEqual(Produto.objects.count(), 4)
        self.assertEqual(Curso.objects.count(), 4)
        self.assertEqual(EtapaCurso.objects.count(), 24)
        self.assertEqual(Questao.objects.count(), 32)
        self.assertEqual(Tecnico.objects.count(), 0)
        self.assertEqual(CursoLiberado.objects.count(), 0)
        self.assertIn("Nenhum técnico foi criado", saida.getvalue())
