from datetime import timedelta
from io import StringIO
import re

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group, User
from django.core import mail
from django.core.management import call_command
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Alternativa,
    ConclusaoTreinamento,
    Curso,
    CursoLiberado,
    Empresa,
    EtapaCurso,
    Produto,
    ProgressoCurso,
    ProgressoEtapa,
    Questao,
    ResponsavelEmpresa,
    Tecnico,
    TentativaAvaliacao,
)
from .admin import (
    ConclusaoTreinamentoAdmin,
    CursoLiberadoAdmin,
    SituacaoVencimentoFilter,
)


class FluxoCursoTest(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(
            username="tecnico@exemplo.com", password="SenhaForte123!"
        )
        self.tecnico = Tecnico.objects.create(
            empresa=Empresa.objects.create(nome="Empresa Exemplo"),
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
        self.assertRegex(conclusao.codigo_certificado, r"^CERT-[0-9A-F]{8}$")
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

    def test_lista_curso_exibe_codigo_do_certificado(self):
        conclusao = ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico,
            curso=self.curso,
            data_conclusao=timezone.localdate(),
        )

        resposta = self.client.get(
            reverse("cursos_por_produto", args=(self.produto.id,))
        )

        self.assertContains(resposta, conclusao.codigo_certificado)


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
        self.assertEqual(Empresa.objects.count(), 0)
        self.assertEqual(Tecnico.objects.count(), 0)
        self.assertEqual(CursoLiberado.objects.count(), 0)
        self.assertIn("Nenhum técnico foi criado", saida.getvalue())

    def test_cria_tecnico_demo_com_empresa(self):
        saida = StringIO()

        call_command("criar_cursos_demonstracao", stdout=saida)

        tecnico = Tecnico.objects.get(email="tecnico.demo@semparar.com.br")
        self.assertEqual(tecnico.empresa.nome, "Sem Parar")
        self.assertEqual(Empresa.objects.count(), 1)


class RedefinirAdminTest(TestCase):
    def test_cria_administrador(self):
        saida = StringIO()

        call_command(
            "redefinir_admin",
            username="admin",
            email="admin@exemplo.com",
            password="SenhaAdmin123!",
            noinput=True,
            stdout=saida,
        )

        usuario = User.objects.get(username="admin")
        self.assertEqual(usuario.email, "admin@exemplo.com")
        self.assertTrue(usuario.is_staff)
        self.assertTrue(usuario.is_superuser)
        self.assertTrue(usuario.is_active)
        self.assertTrue(usuario.check_password("SenhaAdmin123!"))
        self.assertIn("Administrador 'admin' criado", saida.getvalue())

    def test_redefine_administrador_existente(self):
        saida = StringIO()

        User.objects.create_user(
            username="admin",
            email="antigo@exemplo.com",
            password="SenhaAntiga123!",
        )

        call_command(
            "redefinir_admin",
            username="admin",
            email="novo@exemplo.com",
            password="NovaSenhaAdmin123!",
            noinput=True,
            stdout=saida,
        )

        usuario = User.objects.get(username="admin")
        self.assertEqual(usuario.email, "novo@exemplo.com")
        self.assertTrue(usuario.is_staff)
        self.assertTrue(usuario.is_superuser)
        self.assertTrue(usuario.check_password("NovaSenhaAdmin123!"))


class ResponsavelEmpresaTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Cliente Exemplo")
        self.usuario = User.objects.create_user(
            username="responsavel@exemplo.com",
            email="responsavel@exemplo.com",
            password="SenhaForte123!",
        )

    def test_grupos_iniciais_existem(self):
        grupo_operacional = Group.objects.get(name="Responsável operacional")
        grupo_editor = Group.objects.get(name="Editor de cursos")

        permissoes_operacionais = set(
            grupo_operacional.permissions.values_list("codename", flat=True)
        )
        permissoes_editor = set(
            grupo_editor.permissions.values_list("codename", flat=True)
        )

        self.assertTrue(
            {"view_tecnico", "add_cursoliberado", "change_empresa"}.issubset(
                permissoes_operacionais
            )
        )
        self.assertTrue(
            {"view_curso", "add_etapacurso", "change_questao"}.issubset(
                permissoes_editor
            )
        )

    def test_responsavel_ativo_recebe_grupo_do_papel(self):
        ResponsavelEmpresa.objects.create(
            empresa=self.empresa,
            usuario=self.usuario,
            papel=ResponsavelEmpresa.Papel.OPERACIONAL,
        )

        self.assertTrue(
            self.usuario.groups.filter(name="Responsável operacional").exists()
        )

    def test_desativar_responsavel_remove_grupo_sem_outro_vinculo_ativo(self):
        responsavel = ResponsavelEmpresa.objects.create(
            empresa=self.empresa,
            usuario=self.usuario,
            papel=ResponsavelEmpresa.Papel.EDITOR_CURSOS,
        )

        responsavel.ativo = False
        responsavel.save()

        self.assertFalse(self.usuario.groups.filter(name="Editor de cursos").exists())


class OperacaoAdminTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Empresa Operacional")
        self.tecnico = Tecnico.objects.create(
            empresa=self.empresa,
            nome="Técnico Operacional",
            email="operacional@exemplo.com",
            matricula="OP001",
        )
        self.produto = Produto.objects.create(nome="Produto Operacional")
        self.curso = Curso.objects.create(nome="Curso Operacional", produto=self.produto)
        self.site = AdminSite()

    def test_acoes_de_liberacao_em_lote(self):
        liberacao = CursoLiberado.objects.create(
            tecnico=self.tecnico,
            curso=self.curso,
            obrigatorio=True,
            ativo=True,
        )
        admin_liberacao = CursoLiberadoAdmin(CursoLiberado, self.site)
        queryset = CursoLiberado.objects.filter(pk=liberacao.pk)

        admin_liberacao.marcar_como_inativas(None, queryset)
        liberacao.refresh_from_db()
        self.assertFalse(liberacao.ativo)

        admin_liberacao.marcar_como_ativas(None, queryset)
        admin_liberacao.marcar_como_opcionais(None, queryset)
        liberacao.refresh_from_db()
        self.assertTrue(liberacao.ativo)
        self.assertFalse(liberacao.obrigatorio)

        admin_liberacao.marcar_como_obrigatorias(None, queryset)
        liberacao.refresh_from_db()
        self.assertTrue(liberacao.obrigatorio)

    def test_status_e_dias_para_vencer_no_admin(self):
        conclusao = ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico,
            curso=self.curso,
            data_conclusao=timezone.localdate(),
            data_vencimento=timezone.localdate() + timedelta(days=10),
        )
        admin_conclusao = ConclusaoTreinamentoAdmin(
            ConclusaoTreinamento,
            self.site,
        )

        self.assertEqual(
            admin_conclusao.situacao_vencimento(conclusao),
            "Vence em até 30 dias",
        )
        self.assertEqual(admin_conclusao.dias_para_vencer(conclusao), 10)

    def test_conclusao_gera_codigo_certificado_unico(self):
        primeira = ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico,
            curso=self.curso,
            data_conclusao=timezone.localdate(),
        )
        segunda = ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico,
            curso=self.curso,
            data_conclusao=timezone.localdate(),
        )

        self.assertRegex(primeira.codigo_certificado, r"^CERT-[0-9A-F]{8}$")
        self.assertRegex(segunda.codigo_certificado, r"^CERT-[0-9A-F]{8}$")
        self.assertNotEqual(
            primeira.codigo_certificado,
            segunda.codigo_certificado,
        )

    def test_filtro_de_vencimento_no_admin(self):
        ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico,
            curso=self.curso,
            data_conclusao=timezone.localdate() - timedelta(days=40),
            data_vencimento=timezone.localdate() - timedelta(days=1),
        )
        ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico,
            curso=self.curso,
            data_conclusao=timezone.localdate(),
            data_vencimento=timezone.localdate() + timedelta(days=10),
        )
        ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico,
            curso=self.curso,
            data_conclusao=timezone.localdate(),
            data_vencimento=timezone.localdate() + timedelta(days=60),
        )

        admin_conclusao = ConclusaoTreinamentoAdmin(
            ConclusaoTreinamento,
            self.site,
        )
        request = RequestFactory().get(
            "/admin/core/conclusaotreinamento/",
            {"situacao_vencimento": "proximos_30"},
        )
        filtro = SituacaoVencimentoFilter(
            request,
            request.GET.copy(),
            ConclusaoTreinamento,
            admin_conclusao,
        )

        filtradas = filtro.queryset(None, ConclusaoTreinamento.objects.all())

        self.assertEqual(filtradas.count(), 1)
        self.assertEqual(
            filtradas.first().data_vencimento,
            timezone.localdate() + timedelta(days=10),
        )


class ValidacaoCertificadoTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Empresa Certificadora")
        self.tecnico = Tecnico.objects.create(
            empresa=self.empresa,
            nome="Técnico Certificado",
            email="certificado@exemplo.com",
            matricula="CERT001",
        )
        self.produto = Produto.objects.create(nome="Produto Certificado")
        self.curso = Curso.objects.create(
            nome="Curso Certificado",
            produto=self.produto,
        )
        self.conclusao = ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico,
            curso=self.curso,
            data_conclusao=timezone.localdate(),
            data_vencimento=timezone.localdate() + timedelta(days=60),
        )

    def test_pagina_publica_abre_sem_login(self):
        resposta = self.client.get(reverse("validar_certificado"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Validar certificado")

    def test_valida_certificado_existente_por_querystring(self):
        resposta = self.client.get(
            reverse("validar_certificado"),
            {"codigo": self.conclusao.codigo_certificado},
        )

        self.assertContains(resposta, self.conclusao.codigo_certificado)
        self.assertContains(resposta, self.tecnico.nome)
        self.assertContains(resposta, self.empresa.nome)
        self.assertContains(resposta, "Válido")
        self.assertContains(
            resposta,
            reverse("certificado_imprimir", args=(self.conclusao.codigo_certificado,)),
        )

    def test_valida_certificado_por_url_direta(self):
        resposta = self.client.get(
            reverse(
                "validar_certificado_codigo",
                args=(self.conclusao.codigo_certificado,),
            )
        )

        self.assertContains(resposta, self.curso.nome)
        self.assertContains(resposta, self.conclusao.codigo_certificado)

    def test_normaliza_codigo_sem_prefixo(self):
        codigo_sem_prefixo = self.conclusao.codigo_certificado.replace("CERT-", "")

        resposta = self.client.get(
            reverse("validar_certificado"),
            {"codigo": codigo_sem_prefixo.lower()},
        )

        self.assertContains(resposta, self.conclusao.codigo_certificado)

    def test_certificado_inexistente_mostra_estado_nao_encontrado(self):
        resposta = self.client.get(
            reverse("validar_certificado"),
            {"codigo": "CERT-INEXISTE"},
        )

        self.assertContains(resposta, "Certificado não encontrado")
        self.assertContains(resposta, "CERT-INEXISTE")

    def test_certificado_vencido_mostra_situacao_vencida(self):
        conclusao_vencida = ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico,
            curso=self.curso,
            data_conclusao=timezone.localdate() - timedelta(days=90),
            data_vencimento=timezone.localdate() - timedelta(days=1),
        )

        resposta = self.client.get(
            reverse("validar_certificado"),
            {"codigo": conclusao_vencida.codigo_certificado},
        )

        self.assertContains(resposta, "Vencido")

    def test_pagina_imprimivel_do_certificado(self):
        resposta = self.client.get(
            reverse(
                "certificado_imprimir",
                args=(self.conclusao.codigo_certificado,),
            )
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Certificado de conclusão")
        self.assertContains(resposta, self.conclusao.codigo_certificado)
        self.assertContains(resposta, self.tecnico.nome)
        self.assertContains(resposta, self.curso.nome)
        self.assertContains(resposta, "Imprimir ou salvar PDF")

    def test_pagina_imprimivel_inexistente_retorna_404(self):
        resposta = self.client.get(
            reverse("certificado_imprimir", args=("CERT-INEXISTE",))
        )

        self.assertEqual(resposta.status_code, 404)
        self.assertContains(resposta, "Certificado não encontrado", status_code=404)


class RelatorioTreinamentosTest(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="admin-relatorio",
            password="SenhaForte123!",
            is_staff=True,
        )
        self.usuario_comum = User.objects.create_user(
            username="usuario-comum",
            password="SenhaForte123!",
        )
        self.empresa = Empresa.objects.create(nome="Empresa Relatório")
        self.outra_empresa = Empresa.objects.create(nome="Outra Empresa")
        self.tecnico = Tecnico.objects.create(
            empresa=self.empresa,
            nome="Técnico Relatório",
            email="relatorio@exemplo.com",
            matricula="REL001",
        )
        self.outro_tecnico = Tecnico.objects.create(
            empresa=self.outra_empresa,
            nome="Outro Técnico",
            email="outro.relatorio@exemplo.com",
            matricula="REL002",
        )
        self.produto = Produto.objects.create(nome="Produto Relatório")

        self.curso_pendente = self._criar_liberacao("Curso Pendente")
        self.curso_andamento = self._criar_liberacao("Curso Em Andamento")
        self.curso_vencido = self._criar_liberacao("Curso Vencido")
        self.curso_vence_30 = self._criar_liberacao("Curso Vence 30")
        self.curso_em_dia = self._criar_liberacao("Curso Em Dia")
        self.curso_outra_empresa = self._criar_liberacao(
            "Curso Outra Empresa",
            tecnico=self.outro_tecnico,
        )

        ProgressoCurso.objects.create(
            tecnico=self.tecnico,
            curso=self.curso_andamento,
            status=ProgressoCurso.Status.EM_ANDAMENTO,
            iniciado_em=timezone.now(),
        )
        ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico,
            curso=self.curso_vencido,
            data_conclusao=timezone.localdate() - timedelta(days=90),
            data_vencimento=timezone.localdate() - timedelta(days=1),
        )
        ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico,
            curso=self.curso_vence_30,
            data_conclusao=timezone.localdate(),
            data_vencimento=timezone.localdate() + timedelta(days=10),
        )
        ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico,
            curso=self.curso_em_dia,
            data_conclusao=timezone.localdate(),
            data_vencimento=timezone.localdate() + timedelta(days=60),
        )

    def _criar_liberacao(self, nome_curso, tecnico=None):
        curso = Curso.objects.create(nome=nome_curso, produto=self.produto)
        CursoLiberado.objects.create(
            tecnico=tecnico or self.tecnico,
            curso=curso,
            ativo=True,
        )
        return curso

    def test_relatorio_exige_usuario_staff(self):
        resposta_anonima = self.client.get(reverse("relatorio_treinamentos"))
        self.assertEqual(resposta_anonima.status_code, 302)

        self.client.force_login(self.usuario_comum)
        resposta_comum = self.client.get(reverse("relatorio_treinamentos"))
        self.assertEqual(resposta_comum.status_code, 302)

    def test_relatorio_mostra_totais_e_situacoes(self):
        self.client.force_login(self.staff)

        resposta = self.client.get(reverse("relatorio_treinamentos"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Relatório de treinamentos")
        self.assertContains(resposta, "Curso Pendente")
        self.assertContains(resposta, "Curso Em Andamento")
        self.assertContains(resposta, "Curso Vencido")
        self.assertEqual(resposta.context["totais"]["total"], 6)
        self.assertEqual(resposta.context["totais"]["pendente"], 2)
        self.assertEqual(resposta.context["totais"]["em_andamento"], 1)
        self.assertEqual(resposta.context["totais"]["vencido"], 1)
        self.assertEqual(resposta.context["totais"]["vence_30"], 1)
        self.assertEqual(resposta.context["totais"]["em_dia"], 1)

    def test_relatorio_filtra_por_situacao(self):
        self.client.force_login(self.staff)

        resposta = self.client.get(
            reverse("relatorio_treinamentos"),
            {"situacao": "vencido"},
        )

        self.assertEqual(resposta.context["totais"]["total"], 1)
        self.assertContains(resposta, "Curso Vencido")
        self.assertNotContains(resposta, "Curso Pendente")

    def test_relatorio_filtra_por_empresa(self):
        self.client.force_login(self.staff)

        resposta = self.client.get(
            reverse("relatorio_treinamentos"),
            {"empresa": str(self.outra_empresa.id)},
        )

        self.assertEqual(resposta.context["totais"]["total"], 1)
        self.assertContains(resposta, "Curso Outra Empresa")
        self.assertNotContains(resposta, "Curso Pendente")


class LiberarCursoLoteTest(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="admin-liberacao",
            password="SenhaForte123!",
            is_staff=True,
        )
        self.usuario_comum = User.objects.create_user(
            username="usuario-liberacao",
            password="SenhaForte123!",
        )
        self.empresa = Empresa.objects.create(nome="Empresa Liberação")
        self.outra_empresa = Empresa.objects.create(nome="Empresa Fora")
        self.tecnico_1 = Tecnico.objects.create(
            empresa=self.empresa,
            nome="Técnico Um",
            email="tecnico1@exemplo.com",
            matricula="LIB001",
        )
        self.tecnico_2 = Tecnico.objects.create(
            empresa=self.empresa,
            nome="Técnico Dois",
            email="tecnico2@exemplo.com",
            matricula="LIB002",
        )
        self.tecnico_inativo = Tecnico.objects.create(
            empresa=self.empresa,
            nome="Técnico Inativo",
            email="inativo@exemplo.com",
            matricula="LIB003",
            ativo=False,
        )
        self.tecnico_outra_empresa = Tecnico.objects.create(
            empresa=self.outra_empresa,
            nome="Técnico Outra Empresa",
            email="outra@exemplo.com",
            matricula="LIB004",
        )
        self.produto = Produto.objects.create(nome="Produto Liberação")
        self.curso = Curso.objects.create(nome="Curso Liberação", produto=self.produto)

    def test_liberacao_lote_exige_staff(self):
        resposta_anonima = self.client.get(reverse("liberar_curso_lote"))
        self.assertEqual(resposta_anonima.status_code, 302)

        self.client.force_login(self.usuario_comum)
        resposta_comum = self.client.get(reverse("liberar_curso_lote"))
        self.assertEqual(resposta_comum.status_code, 302)

    def test_liberacao_lote_para_todos_tecnicos_ativos_da_empresa(self):
        self.client.force_login(self.staff)

        resposta = self.client.post(
            reverse("liberar_curso_lote"),
            {
                "empresa": self.empresa.id,
                "curso": self.curso.id,
                "todos_tecnicos": "on",
                "obrigatorio": "on",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(
            CursoLiberado.objects.filter(
                tecnico=self.tecnico_1,
                curso=self.curso,
                obrigatorio=True,
                ativo=True,
            ).exists()
        )
        self.assertTrue(
            CursoLiberado.objects.filter(
                tecnico=self.tecnico_2,
                curso=self.curso,
                ativo=True,
            ).exists()
        )
        self.assertFalse(
            CursoLiberado.objects.filter(
                tecnico=self.tecnico_inativo,
                curso=self.curso,
            ).exists()
        )
        self.assertEqual(resposta.context["resultado"]["criados"], 2)

    def test_liberacao_lote_ignora_duplicado_ativo(self):
        CursoLiberado.objects.create(tecnico=self.tecnico_1, curso=self.curso)
        self.client.force_login(self.staff)

        resposta = self.client.post(
            reverse("liberar_curso_lote"),
            {
                "empresa": self.empresa.id,
                "curso": self.curso.id,
                "tecnicos": [self.tecnico_1.id, self.tecnico_2.id],
                "obrigatorio": "on",
            },
        )

        self.assertEqual(CursoLiberado.objects.filter(curso=self.curso).count(), 2)
        self.assertEqual(resposta.context["resultado"]["criados"], 1)
        self.assertEqual(resposta.context["resultado"]["existentes"], 1)

    def test_liberacao_lote_reativa_liberacao_inativa(self):
        CursoLiberado.objects.create(
            tecnico=self.tecnico_1,
            curso=self.curso,
            obrigatorio=False,
            ativo=False,
        )
        self.client.force_login(self.staff)

        resposta = self.client.post(
            reverse("liberar_curso_lote"),
            {
                "empresa": self.empresa.id,
                "curso": self.curso.id,
                "tecnicos": [self.tecnico_1.id],
                "obrigatorio": "on",
            },
        )

        liberacao = CursoLiberado.objects.get(tecnico=self.tecnico_1, curso=self.curso)
        self.assertTrue(liberacao.ativo)
        self.assertTrue(liberacao.obrigatorio)
        self.assertEqual(resposta.context["resultado"]["reativados"], 1)

    def test_liberacao_lote_rejeita_tecnico_de_outra_empresa(self):
        self.client.force_login(self.staff)

        resposta = self.client.post(
            reverse("liberar_curso_lote"),
            {
                "empresa": self.empresa.id,
                "curso": self.curso.id,
                "tecnicos": [self.tecnico_outra_empresa.id],
                "obrigatorio": "on",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(CursoLiberado.objects.filter(curso=self.curso).exists())
        self.assertContains(
            resposta,
            "Selecione ao menos um técnico ou marque a liberação para todos.",
        )
