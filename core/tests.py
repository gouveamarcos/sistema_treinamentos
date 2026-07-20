from datetime import timedelta
from io import StringIO
import os
import re
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group, User
from django.conf import settings
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
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
    EventoAuditoria,
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
    EmpresaAdmin,
    EventoAuditoriaAdmin,
    SituacaoVencimentoFilter,
    TecnicoAdmin,
)
from treinamentos.settings import database_config


class ConfiguracaoSegurancaTest(TestCase):
    def test_defaults_de_seguranca_e_limite_de_importacao(self):
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")
        self.assertEqual(settings.MAX_CSV_IMPORT_SIZE_BYTES, 2 * 1024 * 1024)
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 7 * 24 * 60 * 60)

    def test_database_url_postgres_configura_banco_de_producao(self):
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": (
                    "postgres://usuario:senha@db.exemplo.com:5432/treinamentos"
                ),
                "DB_CONN_MAX_AGE": "120",
                "DB_SSLMODE": "require",
            },
        ):
            config = database_config()

        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["NAME"], "treinamentos")
        self.assertEqual(config["USER"], "usuario")
        self.assertEqual(config["PASSWORD"], "senha")
        self.assertEqual(config["HOST"], "db.exemplo.com")
        self.assertEqual(config["PORT"], "5432")
        self.assertEqual(config["CONN_MAX_AGE"], 120)
        self.assertEqual(config["OPTIONS"]["sslmode"], "require")


class SaudeTest(TestCase):
    def test_endpoint_de_saude_e_publico_e_verifica_banco(self):
        resposta = self.client.get(reverse("saude"))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {"status": "ok", "database": "ok"})


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
        self.produto = Produto.objects.create(
            nome="Abastece",
            empresa=self.tecnico.empresa,
        )
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
            resposta,
            reverse("certificado_imprimir", args=(conclusao.codigo_certificado,)),
        )
        self.assertEqual(progresso.status, ProgressoCurso.Status.APROVADO)
        self.assertIsNotNone(conclusao.data_vencimento)
        self.assertRegex(conclusao.codigo_certificado, r"^CERT-[0-9A-F]{8}$")
        self.assertTrue(
            TentativaAvaliacao.objects.filter(
                progresso=progresso, aprovado=True, nota=100
            ).exists()
        )

    def test_curso_concluido_exibe_atalho_para_certificado(self):
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
        conclusao = ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico,
            curso=self.curso,
            data_conclusao=timezone.localdate(),
        )

        resposta = self.client.get(reverse("curso_detalhe", args=(self.curso.id,)))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Seu certificado está disponível.")
        self.assertContains(resposta, conclusao.codigo_certificado)
        self.assertContains(
            resposta,
            reverse("certificado_imprimir", args=(conclusao.codigo_certificado,)),
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

    def test_superadmin_pode_fazer_curso_com_tecnico_interno(self):
        superadmin = User.objects.create_user(
            username="superadmin-teste-curso",
            password="SenhaForte123!",
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(superadmin)

        resposta = self.client.get(reverse("curso_detalhe", args=(self.curso.id,)))

        tecnico_teste = Tecnico.objects.get(
            matricula=f"TESTE-{superadmin.id}-{self.tecnico.empresa_id}"
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(tecnico_teste.empresa, self.tecnico.empresa)
        self.assertTrue(
            CursoLiberado.objects.filter(
                tecnico=tecnico_teste,
                curso=self.curso,
                ativo=True,
            ).exists()
        )
        self.assertContains(resposta, self.aula.titulo)

    def test_editor_pode_fazer_curso_da_empresa_como_teste(self):
        editor = User.objects.create_user(
            username="editor-teste-curso",
            password="SenhaForte123!",
            is_staff=True,
        )
        ResponsavelEmpresa.objects.create(
            empresa=self.tecnico.empresa,
            usuario=editor,
            papel=ResponsavelEmpresa.Papel.EDITOR_CURSOS,
        )
        self.client.force_login(editor)

        resposta = self.client.get(
            reverse("cursos_por_produto", args=(self.produto.id,))
        )

        tecnico_teste = Tecnico.objects.get(
            matricula=f"TESTE-{editor.id}-{self.tecnico.empresa_id}"
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, self.curso.nome)
        self.assertTrue(
            CursoLiberado.objects.filter(
                tecnico=tecnico_teste,
                curso=self.curso,
                ativo=True,
            ).exists()
        )


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
        self.assertEqual(Empresa.objects.count(), 1)
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


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="Academia Tecnica <teste@exemplo.com>",
)
class GestaoResponsaveisEmpresaTest(TestCase):
    def setUp(self):
        self.empresa_a = Empresa.objects.create(nome="Cliente A")
        self.empresa_b = Empresa.objects.create(nome="Cliente B")
        self.superadmin = User.objects.create_user(
            username="superadmin-responsaveis",
            password="SenhaForte123!",
            is_staff=True,
            is_superuser=True,
        )
        self.responsavel_a = User.objects.create_user(
            username="gestor-a",
            email="gestor.a@exemplo.com",
            password="SenhaForte123!",
            is_staff=True,
        )
        self.vinculo_a = ResponsavelEmpresa.objects.create(
            empresa=self.empresa_a,
            usuario=self.responsavel_a,
            papel=ResponsavelEmpresa.Papel.OPERACIONAL,
        )
        self.responsavel_b = User.objects.create_user(
            username="gestor-b",
            email="gestor.b@exemplo.com",
            password="SenhaForte123!",
            is_staff=True,
        )
        self.vinculo_b = ResponsavelEmpresa.objects.create(
            empresa=self.empresa_b,
            usuario=self.responsavel_b,
            papel=ResponsavelEmpresa.Papel.OPERACIONAL,
        )

    def test_superadmin_cadastra_responsavel_e_cria_usuario_staff(self):
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("responsaveis_empresas"),
            {
                "empresa": self.empresa_a.id,
                "nome": "Novo Responsavel",
                "email": "novo.responsavel@exemplo.com",
                "papel": ResponsavelEmpresa.Papel.EDITOR_CURSOS,
                "ativo": "on",
            },
            follow=True,
        )

        usuario = User.objects.get(email="novo.responsavel@exemplo.com")
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(usuario.is_staff)
        self.assertFalse(usuario.has_usable_password())
        self.assertTrue(
            ResponsavelEmpresa.objects.filter(
                empresa=self.empresa_a,
                usuario=usuario,
                papel=ResponsavelEmpresa.Papel.EDITOR_CURSOS,
                ativo=True,
            ).exists()
        )
        self.assertTrue(usuario.groups.filter(name__icontains="Editor").exists())
        self.assertContains(resposta, "novo.responsavel@exemplo.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("novo.responsavel@exemplo.com", mail.outbox[0].to)
        self.assertIn("definir sua senha", mail.outbox[0].body)
        self.assertIn("/senha/redefinir/", mail.outbox[0].body)
        self.assertNotIn("nao esperava este convite", mail.outbox[0].body)

    def test_responsavel_enxerga_apenas_vinculos_da_propria_empresa(self):
        self.client.force_login(self.responsavel_a)

        resposta = self.client.get(reverse("responsaveis_empresas"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "gestor.a@exemplo.com")
        self.assertNotContains(resposta, "gestor.b@exemplo.com")
        self.assertQuerySetEqual(
            resposta.context["form"].fields["empresa"].queryset,
            [self.empresa_a],
            transform=lambda empresa: empresa,
        )

    def test_responsavel_nao_edita_vinculo_de_outra_empresa(self):
        self.client.force_login(self.responsavel_a)

        resposta = self.client.get(
            reverse("editar_responsavel_empresa", args=(self.vinculo_b.id,))
        )

        self.assertEqual(resposta.status_code, 404)

    def test_edicao_atualiza_papel_e_status(self):
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("editar_responsavel_empresa", args=(self.vinculo_a.id,)),
            {
                "empresa": self.empresa_a.id,
                "nome": "Gestor Atualizado",
                "email": self.responsavel_a.email,
                "papel": ResponsavelEmpresa.Papel.EDITOR_CURSOS,
                "ativo": "on",
            },
            follow=True,
        )

        self.vinculo_a.refresh_from_db()
        self.responsavel_a.refresh_from_db()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.vinculo_a.papel, ResponsavelEmpresa.Papel.EDITOR_CURSOS)
        self.assertTrue(self.vinculo_a.ativo)
        self.assertEqual(self.responsavel_a.first_name, "Gestor Atualizado")
        self.assertTrue(
            self.responsavel_a.groups.filter(name__icontains="Editor").exists()
        )
        self.assertFalse(
            self.responsavel_a.groups.filter(name__icontains="operacional").exists()
        )

    def test_alternar_responsavel_desativa_e_reativa(self):
        self.client.force_login(self.superadmin)

        resposta_desativar = self.client.post(
            reverse("alternar_responsavel_empresa", args=(self.vinculo_a.id,)),
            follow=True,
        )
        self.vinculo_a.refresh_from_db()
        self.responsavel_a.refresh_from_db()

        self.assertEqual(resposta_desativar.status_code, 200)
        self.assertFalse(self.vinculo_a.ativo)
        self.assertFalse(
            self.responsavel_a.groups.filter(name__icontains="operacional").exists()
        )

        self.client.post(
            reverse("alternar_responsavel_empresa", args=(self.vinculo_a.id,)),
            follow=True,
        )
        self.vinculo_a.refresh_from_db()
        self.responsavel_a.refresh_from_db()

        self.assertTrue(self.vinculo_a.ativo)
        self.assertTrue(
            self.responsavel_a.groups.filter(name__icontains="operacional").exists()
        )

    def test_reenvia_convite_para_responsavel(self):
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("reenviar_convite_responsavel", args=(self.vinculo_a.id,)),
            follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.responsavel_a.email, mail.outbox[0].to)
        self.assertIn("/senha/redefinir/", mail.outbox[0].body)
        self.assertNotIn("nao esperava este convite", mail.outbox[0].body)


class ExperienciaResponsavelTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(
            nome="Cliente Experiencia",
            responsavel="Contato Experiencia",
        )
        self.operacional = User.objects.create_user(
            username="operacional-experiencia",
            password="SenhaForte123!",
            is_staff=True,
        )
        ResponsavelEmpresa.objects.create(
            empresa=self.empresa,
            usuario=self.operacional,
            papel=ResponsavelEmpresa.Papel.OPERACIONAL,
        )
        self.editor = User.objects.create_user(
            username="editor-experiencia",
            password="SenhaForte123!",
            is_staff=True,
        )
        ResponsavelEmpresa.objects.create(
            empresa=self.empresa,
            usuario=self.editor,
            papel=ResponsavelEmpresa.Papel.EDITOR_CURSOS,
        )
        self.superadmin = User.objects.create_user(
            username="superadmin-experiencia",
            password="SenhaForte123!",
            is_staff=True,
            is_superuser=True,
        )
        self.produto = Produto.objects.create(
            nome="Produto Experiencia",
            empresa=self.empresa,
        )
        self.curso = Curso.objects.create(nome="Curso Experiencia", produto=self.produto)
        self.tecnico = Tecnico.objects.create(
            empresa=self.empresa,
            nome="Tecnico Experiencia",
            email="experiencia@exemplo.com",
            matricula="EXP001",
        )
        CursoLiberado.objects.create(tecnico=self.tecnico, curso=self.curso)

    def test_home_do_operacional_mostra_painel_e_apenas_atalhos_operacionais(self):
        self.client.force_login(self.operacional)

        resposta = self.client.get(reverse("home"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Painel operacional")
        self.assertContains(resposta, "Liberar cursos")
        self.assertContains(resposta, "Relatórios")
        self.assertContains(resposta, "Técnicos")
        self.assertNotContains(resposta, reverse("produtos_operacionais"))
        self.assertNotContains(resposta, "Editor de cursos")

    def test_home_do_editor_mostra_catalogo_e_oculta_operacao(self):
        self.client.force_login(self.editor)

        resposta = self.client.get(reverse("home"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Painel operacional")
        self.assertContains(resposta, "Editor de cursos")
        self.assertContains(resposta, "Cursos")
        self.assertNotContains(resposta, "Organize as linhas de produto do catálogo.")
        self.assertNotContains(resposta, "Liberar cursos")
        self.assertNotContains(resposta, "Relatorios")

    def test_superadmin_ve_operacao_e_catalogo(self):
        self.client.force_login(self.superadmin)

        resposta = self.client.get(reverse("home"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Painel do superadmin")
        self.assertContains(resposta, "Gerenciar empresas")
        self.assertContains(resposta, reverse("empresas_operacionais"))
        self.assertContains(resposta, "Acessar painel da empresa")
        self.assertNotContains(resposta, reverse("tecnicos_operacionais"))
        self.assertNotContains(resposta, reverse("liberar_curso_lote"))
        self.assertNotContains(resposta, reverse("cursos_operacionais"))

    def test_superadmin_acessa_painel_dedicado_da_empresa(self):
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("acessar_empresa_operacional", args=(self.empresa.id,)),
            follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, self.empresa.nome)
        self.assertContains(resposta, reverse("tecnicos_operacionais"))
        self.assertContains(resposta, reverse("liberar_curso_lote"))
        self.assertNotContains(resposta, "Empresas visíveis")
        self.assertNotContains(resposta, "Acessar painel da empresa")

    def test_home_do_superadmin_continua_sendo_lobby_apos_acessar_empresa(self):
        self.client.force_login(self.superadmin)
        self.client.post(reverse("acessar_empresa_operacional", args=(self.empresa.id,)))

        resposta = self.client.get(reverse("home"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Painel do superadmin")
        self.assertContains(resposta, "Acessar painel da empresa")

    def test_editor_nao_acessa_tela_operacional_por_url_direta(self):
        self.client.force_login(self.editor)

        resposta = self.client.get(reverse("relatorio_treinamentos"))

        self.assertEqual(resposta.status_code, 403)

    def test_operacional_nao_acessa_catalogo_por_url_direta(self):
        self.client.force_login(self.operacional)

        resposta = self.client.get(reverse("produtos_operacionais"))

        self.assertEqual(resposta.status_code, 403)


class AuditoriaOperacionalTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Cliente Auditoria")
        self.outra_empresa = Empresa.objects.create(nome="Outra Auditoria")
        self.superadmin = User.objects.create_user(
            username="superadmin-auditoria",
            password="SenhaForte123!",
            is_staff=True,
            is_superuser=True,
        )
        self.responsavel = User.objects.create_user(
            username="responsavel-auditoria",
            password="SenhaForte123!",
            is_staff=True,
        )
        ResponsavelEmpresa.objects.create(
            empresa=self.empresa,
            usuario=self.responsavel,
            papel=ResponsavelEmpresa.Papel.OPERACIONAL,
        )
        self.produto = Produto.objects.create(
            nome="Produto Auditoria",
            empresa=self.empresa,
        )
        self.curso = Curso.objects.create(nome="Curso Auditoria", produto=self.produto)
        self.tecnico = Tecnico.objects.create(
            empresa=self.empresa,
            nome="Tecnico Auditoria",
            email="auditoria@exemplo.com",
            matricula="AUD001",
        )
        self.tecnico_outra_empresa = Tecnico.objects.create(
            empresa=self.outra_empresa,
            nome="Tecnico Outra Auditoria",
            email="auditoria.outra@exemplo.com",
            matricula="AUD002",
        )
        self.site = AdminSite()

    def test_registra_evento_ao_liberar_curso_manualmente(self):
        self.client.force_login(self.responsavel)

        resposta = self.client.post(
            reverse("liberar_curso_lote"),
            {
                "empresa": self.empresa.id,
                "curso": self.curso.id,
                "tecnicos": [self.tecnico.id],
                "obrigatorio": "on",
            },
            follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        evento = EventoAuditoria.objects.get(acao=EventoAuditoria.Acao.LIBERACAO)
        self.assertEqual(evento.usuario, self.responsavel)
        self.assertEqual(evento.empresa, self.empresa)
        self.assertEqual(evento.alvo_repr, self.curso.nome)
        self.assertIn("Liberacao manual", evento.detalhes)

    def test_registra_evento_ao_importar_tecnicos(self):
        self.client.force_login(self.responsavel)
        arquivo = SimpleUploadedFile(
            "tecnicos.csv",
            "nome,email,matricula\nTecnico CSV,csv.audit@exemplo.com,AUDCSV\n".encode(),
            content_type="text/csv",
        )

        resposta = self.client.post(
            reverse("importar_tecnicos_operacionais"),
            {"empresa": self.empresa.id, "arquivo": arquivo},
            follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        evento = EventoAuditoria.objects.get(acao=EventoAuditoria.Acao.IMPORTACAO)
        self.assertEqual(evento.usuario, self.responsavel)
        self.assertEqual(evento.empresa, self.empresa)
        self.assertIn("Importacao CSV de tecnicos", evento.detalhes)

    def test_admin_de_auditoria_respeita_escopo_da_empresa(self):
        EventoAuditoria.objects.create(
            usuario=self.superadmin,
            empresa=self.empresa,
            acao=EventoAuditoria.Acao.STATUS,
            alvo_tipo="Tecnico",
            alvo_id=self.tecnico.id,
            alvo_repr=str(self.tecnico),
        )
        EventoAuditoria.objects.create(
            usuario=self.superadmin,
            empresa=self.outra_empresa,
            acao=EventoAuditoria.Acao.STATUS,
            alvo_tipo="Tecnico",
            alvo_id=self.tecnico_outra_empresa.id,
            alvo_repr=str(self.tecnico_outra_empresa),
        )
        request = RequestFactory().get("/admin/core/eventoauditoria/")
        request.user = self.responsavel
        admin_auditoria = EventoAuditoriaAdmin(EventoAuditoria, self.site)

        queryset = admin_auditoria.get_queryset(request)

        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().empresa, self.empresa)

    def test_tela_historico_respeita_escopo(self):
        EventoAuditoria.objects.create(
            usuario=self.superadmin,
            empresa=self.empresa,
            acao=EventoAuditoria.Acao.LIBERACAO,
            alvo_tipo="Curso",
            alvo_id=self.curso.id,
            alvo_repr="Curso Visivel",
            detalhes="Evento visivel",
        )
        EventoAuditoria.objects.create(
            usuario=self.superadmin,
            empresa=self.outra_empresa,
            acao=EventoAuditoria.Acao.LIBERACAO,
            alvo_tipo="Curso",
            alvo_id=self.curso.id,
            alvo_repr="Curso Oculto",
            detalhes="Evento oculto",
        )
        self.client.force_login(self.responsavel)

        resposta = self.client.get(reverse("historico_operacional"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Curso Visivel")
        self.assertNotContains(resposta, "Curso Oculto")

    def test_tela_historico_filtra_por_acao_e_busca(self):
        EventoAuditoria.objects.create(
            usuario=self.responsavel,
            empresa=self.empresa,
            acao=EventoAuditoria.Acao.IMPORTACAO,
            alvo_tipo="Empresa",
            alvo_id=self.empresa.id,
            alvo_repr="Importacao Tecnicos",
            detalhes="Importacao CSV de tecnicos",
        )
        EventoAuditoria.objects.create(
            usuario=self.responsavel,
            empresa=self.empresa,
            acao=EventoAuditoria.Acao.STATUS,
            alvo_tipo="Tecnico",
            alvo_id=self.tecnico.id,
            alvo_repr="Alteracao Status",
            detalhes="Status alterado",
        )
        self.client.force_login(self.responsavel)

        resposta = self.client.get(
            reverse("historico_operacional"),
            {"acao": EventoAuditoria.Acao.IMPORTACAO, "q": "CSV"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Importacao Tecnicos")
        self.assertNotContains(resposta, "Alteracao Status")

    def test_editor_de_cursos_nao_acessa_historico_operacional(self):
        editor = User.objects.create_user(
            username="editor-historico",
            password="SenhaForte123!",
            is_staff=True,
        )
        ResponsavelEmpresa.objects.create(
            empresa=self.empresa,
            usuario=editor,
            papel=ResponsavelEmpresa.Papel.EDITOR_CURSOS,
        )
        self.client.force_login(editor)

        resposta = self.client.get(reverse("historico_operacional"))

        self.assertEqual(resposta.status_code, 403)


class CadastroOperacionalTest(TestCase):
    def setUp(self):
        self.empresa_a = Empresa.objects.create(
            nome="Cliente Cadastro A",
            responsavel="Contato A",
        )
        self.empresa_b = Empresa.objects.create(nome="Cliente Cadastro B")
        self.superadmin = User.objects.create_user(
            username="superadmin-cadastros",
            password="SenhaForte123!",
            is_staff=True,
            is_superuser=True,
        )
        self.responsavel_a = User.objects.create_user(
            username="responsavel-cadastro-a",
            password="SenhaForte123!",
            is_staff=True,
        )
        ResponsavelEmpresa.objects.create(
            empresa=self.empresa_a,
            usuario=self.responsavel_a,
            papel=ResponsavelEmpresa.Papel.OPERACIONAL,
        )
        self.tecnico_a = Tecnico.objects.create(
            empresa=self.empresa_a,
            nome="Tecnico Cadastro A",
            email="cadastro.a@exemplo.com",
            matricula="CAD-A",
        )
        self.tecnico_b = Tecnico.objects.create(
            empresa=self.empresa_b,
            nome="Tecnico Cadastro B",
            email="cadastro.b@exemplo.com",
            matricula="CAD-B",
        )

    def test_superadmin_cria_empresa_pela_tela_operacional(self):
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("empresas_operacionais"),
            {
                "nome": "Cliente Novo",
                "documento": "123",
                "responsavel": "Novo Contato",
                "email": "cliente.novo@exemplo.com",
                "telefone": "11999999999",
                "ativa": "on",
            },
            follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(Empresa.objects.filter(nome="Cliente Novo").exists())
        self.assertContains(resposta, "Cliente Novo")
        self.assertContains(resposta, "Empresa Cliente Novo criada com sucesso.")

    def test_responsavel_nao_cria_empresa(self):
        self.client.force_login(self.responsavel_a)

        resposta = self.client.post(
            reverse("empresas_operacionais"),
            {
                "nome": "Empresa Indevida",
                "ativa": "on",
            },
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(Empresa.objects.filter(nome="Empresa Indevida").exists())

    def test_responsavel_lista_apenas_empresas_do_escopo(self):
        self.client.force_login(self.responsavel_a)

        resposta = self.client.get(reverse("empresas_operacionais"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, self.empresa_a.nome)
        self.assertNotContains(resposta, self.empresa_b.nome)
        self.assertFalse(resposta.context["pode_criar"])

    def test_superadmin_lista_empresa_inativa_para_reativar(self):
        self.empresa_a.ativa = False
        self.empresa_a.save(update_fields=["ativa"])
        self.client.force_login(self.superadmin)

        resposta = self.client.get(reverse("empresas_operacionais"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, self.empresa_a.nome)
        self.assertContains(resposta, "Inativa")
        self.assertContains(resposta, "Ativar")

    def test_superadmin_reativa_empresa_inativa_pela_tela_operacional(self):
        self.empresa_a.ativa = False
        self.empresa_a.save(update_fields=["ativa"])
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("alternar_empresa_operacional", args=(self.empresa_a.id,)),
            follow=True,
        )

        self.empresa_a.refresh_from_db()
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(self.empresa_a.ativa)
        self.assertContains(resposta, "Empresa ativada com sucesso.")

    def test_superadmin_exclui_empresa_sem_vinculos(self):
        empresa = Empresa.objects.create(nome="Cliente Sem Vinculos")
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("excluir_empresa_operacional", args=(empresa.id,)),
            follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Empresa.objects.filter(pk=empresa.id).exists())
        self.assertContains(resposta, "Empresa Cliente Sem Vinculos excluida com sucesso.")
        self.assertTrue(
            EventoAuditoria.objects.filter(
                alvo_tipo="Empresa",
                alvo_repr="Cliente Sem Vinculos",
                detalhes__contains="Empresa excluida",
            ).exists()
        )

    def test_responsavel_nao_exclui_empresa(self):
        empresa = Empresa.objects.create(nome="Cliente Protegido")
        self.client.force_login(self.responsavel_a)

        resposta = self.client.post(
            reverse("excluir_empresa_operacional", args=(empresa.id,))
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(Empresa.objects.filter(pk=empresa.id).exists())

    def test_empresa_com_vinculos_nao_e_excluida(self):
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("excluir_empresa_operacional", args=(self.empresa_a.id,)),
            follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(Empresa.objects.filter(pk=self.empresa_a.id).exists())
        self.assertContains(resposta, "nao pode ser excluida")

    def test_responsavel_edita_empresa_do_proprio_escopo(self):
        self.client.force_login(self.responsavel_a)

        resposta = self.client.post(
            reverse("editar_empresa_operacional", args=(self.empresa_a.id,)),
            {
                "nome": self.empresa_a.nome,
                "documento": "456",
                "responsavel": "Contato Atualizado",
                "email": "contato.a@exemplo.com",
                "telefone": "11888888888",
                "ativa": "on",
            },
            follow=True,
        )

        self.empresa_a.refresh_from_db()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.empresa_a.responsavel, "Contato Atualizado")
        self.assertContains(
            resposta,
            f"Empresa {self.empresa_a.nome} atualizada com sucesso.",
        )

    def test_responsavel_nao_edita_empresa_fora_do_escopo(self):
        self.client.force_login(self.responsavel_a)

        resposta = self.client.get(
            reverse("editar_empresa_operacional", args=(self.empresa_b.id,))
        )

        self.assertEqual(resposta.status_code, 404)

    def test_superadmin_cria_tecnico_pela_tela_operacional(self):
        self.client.force_login(self.superadmin)

        resposta = self.client.post(
            reverse("tecnicos_operacionais"),
            {
                "empresa": self.empresa_b.id,
                "nome": "Tecnico Novo",
                "email": "tecnico.novo@exemplo.com",
                "matricula": "CAD-NOVO",
                "telefone": "11777777777",
                "equipe": "Campo",
                "regiao": "Sudeste",
                "ativo": "on",
            },
            follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(
            Tecnico.objects.filter(
                empresa=self.empresa_b,
                email="tecnico.novo@exemplo.com",
            ).exists()
        )

    def test_responsavel_cria_tecnico_apenas_no_proprio_escopo(self):
        self.client.force_login(self.responsavel_a)

        resposta_get = self.client.get(reverse("tecnicos_operacionais"))
        form = resposta_get.context["form"]
        self.assertQuerySetEqual(
            form.fields["empresa"].queryset,
            [self.empresa_a],
            transform=lambda empresa: empresa,
        )

        resposta_post = self.client.post(
            reverse("tecnicos_operacionais"),
            {
                "empresa": self.empresa_b.id,
                "nome": "Tecnico Fora",
                "email": "tecnico.fora@exemplo.com",
                "matricula": "CAD-FORA",
                "ativo": "on",
            },
        )

        self.assertEqual(resposta_post.status_code, 200)
        self.assertFalse(Tecnico.objects.filter(email="tecnico.fora@exemplo.com").exists())

    def test_responsavel_nao_edita_tecnico_fora_do_escopo(self):
        self.client.force_login(self.responsavel_a)

        resposta = self.client.get(
            reverse("editar_tecnico_operacional", args=(self.tecnico_b.id,))
        )

        self.assertEqual(resposta.status_code, 404)

    def test_responsavel_alterna_tecnico_do_proprio_escopo(self):
        self.client.force_login(self.responsavel_a)

        resposta = self.client.post(
            reverse("alternar_tecnico_operacional", args=(self.tecnico_a.id,)),
            follow=True,
        )

        self.tecnico_a.refresh_from_db()
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(self.tecnico_a.ativo)

    def test_superadmin_importa_tecnicos_por_csv(self):
        self.client.force_login(self.superadmin)
        arquivo = SimpleUploadedFile(
            "tecnicos.csv",
            (
                "nome,email,matricula,telefone,equipe,regiao,ativo\n"
                "Tecnico Importado,importado@exemplo.com,IMP001,11999999999,Campo,Sul,sim\n"
                "Tecnico Inativo,inativo.importado@exemplo.com,IMP002,,,Norte,nao\n"
            ).encode(),
            content_type="text/csv",
        )

        resposta = self.client.post(
            reverse("importar_tecnicos_operacionais"),
            {"empresa": self.empresa_b.id, "arquivo": arquivo},
            follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(
            Tecnico.objects.filter(
                empresa=self.empresa_b,
                matricula="IMP001",
                ativo=True,
            ).exists()
        )
        self.assertTrue(
            Tecnico.objects.filter(
                empresa=self.empresa_b,
                matricula="IMP002",
                ativo=False,
            ).exists()
        )

    @override_settings(MAX_CSV_IMPORT_SIZE_BYTES=10)
    def test_importacao_tecnicos_rejeita_csv_acima_do_limite(self):
        self.client.force_login(self.superadmin)
        arquivo = SimpleUploadedFile(
            "tecnicos.csv",
            (
                "nome,email,matricula\n"
                "Tecnico Grande,grande.import@exemplo.com,IMP-GRANDE\n"
            ).encode(),
            content_type="text/csv",
        )

        resposta = self.client.post(
            reverse("importar_tecnicos_operacionais"),
            {"empresa": self.empresa_a.id, "arquivo": arquivo},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Arquivo CSV muito grande")
        self.assertFalse(
            Tecnico.objects.filter(email="grande.import@exemplo.com").exists()
        )

    def test_importacao_atualiza_tecnico_existente_por_matricula(self):
        self.client.force_login(self.superadmin)
        arquivo = SimpleUploadedFile(
            "tecnicos.csv",
            (
                "nome,email,matricula,telefone,equipe,regiao,ativo\n"
                "Tecnico Atualizado,novo.cadastro.a@exemplo.com,CAD-A,11888888888,Equipe Nova,Leste,sim\n"
            ).encode(),
            content_type="text/csv",
        )

        resposta = self.client.post(
            reverse("importar_tecnicos_operacionais"),
            {"empresa": self.empresa_a.id, "arquivo": arquivo},
            follow=True,
        )

        self.tecnico_a.refresh_from_db()
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.tecnico_a.nome, "Tecnico Atualizado")
        self.assertEqual(self.tecnico_a.email, "novo.cadastro.a@exemplo.com")
        self.assertEqual(self.tecnico_a.equipe, "Equipe Nova")

    def test_responsavel_nao_importa_tecnicos_para_empresa_fora_do_escopo(self):
        self.client.force_login(self.responsavel_a)
        arquivo = SimpleUploadedFile(
            "tecnicos.csv",
            "nome,email,matricula\nTecnico Fora,fora.import@exemplo.com,FORA-IMP\n".encode(),
            content_type="text/csv",
        )

        resposta = self.client.post(
            reverse("importar_tecnicos_operacionais"),
            {"empresa": self.empresa_b.id, "arquivo": arquivo},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(
            Tecnico.objects.filter(email="fora.import@exemplo.com").exists()
        )
        self.assertContains(resposta, "Faça uma escolha válida", html=False)

    def test_importacao_com_erro_nao_grava_linhas_validas(self):
        self.client.force_login(self.superadmin)
        arquivo = SimpleUploadedFile(
            "tecnicos.csv",
            (
                "nome,email,matricula\n"
                "Tecnico Valido,valido.import@exemplo.com,IMP-VALIDO\n"
                ",sem.nome@exemplo.com,IMP-ERRO\n"
            ).encode(),
            content_type="text/csv",
        )

        resposta = self.client.post(
            reverse("importar_tecnicos_operacionais"),
            {"empresa": self.empresa_a.id, "arquivo": arquivo},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Linha 3: nome e obrigatorio.")
        self.assertFalse(
            Tecnico.objects.filter(email="valido.import@exemplo.com").exists()
        )


class CatalogoOperacionalTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Cliente Catalogo")
        self.superadmin = User.objects.create_user(
            username="superadmin-catalogo",
            password="SenhaForte123!",
            is_staff=True,
            is_superuser=True,
        )
        self.editor = User.objects.create_user(
            username="editor-catalogo",
            password="SenhaForte123!",
            is_staff=True,
        )
        ResponsavelEmpresa.objects.create(
            empresa=self.empresa,
            usuario=self.editor,
            papel=ResponsavelEmpresa.Papel.EDITOR_CURSOS,
        )
        self.operacional = User.objects.create_user(
            username="operacional-catalogo",
            password="SenhaForte123!",
            is_staff=True,
        )
        ResponsavelEmpresa.objects.create(
            empresa=self.empresa,
            usuario=self.operacional,
            papel=ResponsavelEmpresa.Papel.OPERACIONAL,
        )
        self.produto = Produto.objects.create(
            empresa=self.empresa,
            nome="Produto Catalogo",
            descricao="Descricao inicial",
        )
        self.curso = Curso.objects.create(
            produto=self.produto,
            nome="Curso Catalogo",
            descricao="Curso inicial",
            validade_meses=12,
            nota_minima=80,
        )

    def test_editor_cria_produto(self):
        self.client.force_login(self.editor)

        resposta = self.client.post(
            reverse("produtos_operacionais"),
            {
                "nome": "Produto Novo",
                "descricao": "Linha nova",
                "ativo": "on",
            },
            follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(Produto.objects.filter(nome="Produto Novo").exists())
        self.assertContains(resposta, "Produto Novo")

    def test_operacional_nao_acessa_catalogo_de_produtos(self):
        self.client.force_login(self.operacional)

        resposta = self.client.get(reverse("produtos_operacionais"))

        self.assertEqual(resposta.status_code, 403)

    def test_editor_edita_e_alterna_produto(self):
        self.client.force_login(self.editor)

        resposta_edicao = self.client.post(
            reverse("editar_produto_operacional", args=(self.produto.id,)),
            {
                "nome": "Produto Atualizado",
                "descricao": "Descricao atualizada",
                "ativo": "on",
            },
            follow=True,
        )
        self.produto.refresh_from_db()

        self.assertEqual(resposta_edicao.status_code, 200)
        self.assertEqual(self.produto.nome, "Produto Atualizado")

        self.client.post(
            reverse("alternar_produto_operacional", args=(self.produto.id,)),
            follow=True,
        )
        self.produto.refresh_from_db()

        self.assertFalse(self.produto.ativo)

    def test_editor_cria_curso(self):
        self.client.force_login(self.editor)

        resposta = self.client.post(
            reverse("cursos_operacionais"),
            {
                "produto": self.produto.id,
                "nome": "Curso Novo",
                "descricao": "Conteudo do curso",
                "validade_meses": 18,
                "nota_minima": 75,
                "link_notebooklm": "",
                "ativo": "on",
            },
            follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(
            Curso.objects.filter(produto=self.produto, nome="Curso Novo").exists()
        )
        self.assertContains(resposta, "Curso Novo")

    def test_editor_cria_curso_com_pdf(self):
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        self.client.force_login(self.editor)
        arquivo = SimpleUploadedFile(
            "manual.pdf",
            b"%PDF-1.4\nconteudo de teste\n%%EOF",
            content_type="application/pdf",
        )

        with override_settings(MEDIA_ROOT=media_root):
            resposta = self.client.post(
                reverse("cursos_operacionais"),
                {
                    "produto": self.produto.id,
                    "nome": "Curso com PDF",
                    "descricao": "Conteudo com PDF",
                    "validade_meses": 18,
                    "nota_minima": 75,
                    "link_notebooklm": "",
                    "material_pdf": arquivo,
                    "ativo": "on",
                },
                follow=True,
            )

            curso = Curso.objects.get(nome="Curso com PDF")

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(curso.material_pdf.name.endswith(".pdf"))

    def test_operacional_nao_acessa_catalogo_de_cursos(self):
        self.client.force_login(self.operacional)

        resposta = self.client.get(reverse("cursos_operacionais"))

        self.assertEqual(resposta.status_code, 403)

    def test_superadmin_edita_e_alterna_curso(self):
        self.client.force_login(self.superadmin)

        resposta_edicao = self.client.post(
            reverse("editar_curso_operacional", args=(self.curso.id,)),
            {
                "produto": self.produto.id,
                "nome": "Curso Atualizado",
                "descricao": "Descricao atualizada",
                "validade_meses": 24,
                "nota_minima": 90,
                "link_notebooklm": "https://example.com/material",
                "ativo": "on",
            },
            follow=True,
        )
        self.curso.refresh_from_db()

        self.assertEqual(resposta_edicao.status_code, 200)
        self.assertEqual(self.curso.nome, "Curso Atualizado")
        self.assertEqual(self.curso.validade_meses, 24)
        self.assertEqual(self.curso.nota_minima, 90)

        self.client.post(
            reverse("alternar_curso_operacional", args=(self.curso.id,)),
            follow=True,
        )
        self.curso.refresh_from_db()

        self.assertFalse(self.curso.ativo)

    def test_registra_auditoria_ao_criar_produto_e_curso(self):
        self.client.force_login(self.editor)

        self.client.post(
            reverse("produtos_operacionais"),
            {
                "nome": "Produto Auditado",
                "descricao": "Auditoria",
                "ativo": "on",
            },
            follow=True,
        )
        produto = Produto.objects.get(nome="Produto Auditado")

        self.client.post(
            reverse("cursos_operacionais"),
            {
                "produto": produto.id,
                "nome": "Curso Auditado",
                "descricao": "Curso com auditoria",
                "validade_meses": 12,
                "nota_minima": 80,
                "link_notebooklm": "",
                "ativo": "on",
            },
            follow=True,
        )

        self.assertTrue(
            EventoAuditoria.objects.filter(
                usuario=self.editor,
                acao=EventoAuditoria.Acao.CADASTRO,
                alvo_tipo="Produto",
                alvo_repr="Produto Auditado",
            ).exists()
        )
        self.assertTrue(
            EventoAuditoria.objects.filter(
                usuario=self.editor,
                acao=EventoAuditoria.Acao.CADASTRO,
                alvo_tipo="Curso",
                alvo_repr="Curso Auditado",
            ).exists()
        )


class ConteudoCursoOperacionalTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Cliente Conteudo")
        self.editor = User.objects.create_user(
            username="editor-conteudo",
            password="SenhaForte123!",
            is_staff=True,
        )
        ResponsavelEmpresa.objects.create(
            empresa=self.empresa,
            usuario=self.editor,
            papel=ResponsavelEmpresa.Papel.EDITOR_CURSOS,
        )
        self.operacional = User.objects.create_user(
            username="operacional-conteudo",
            password="SenhaForte123!",
            is_staff=True,
        )
        ResponsavelEmpresa.objects.create(
            empresa=self.empresa,
            usuario=self.operacional,
            papel=ResponsavelEmpresa.Papel.OPERACIONAL,
        )
        self.produto = Produto.objects.create(
            nome="Produto Conteudo",
            empresa=self.empresa,
        )
        self.curso = Curso.objects.create(nome="Curso Conteudo", produto=self.produto)
        self.etapa_texto = EtapaCurso.objects.create(
            curso=self.curso,
            titulo="Etapa Texto",
            tipo=EtapaCurso.Tipo.TEXTO,
            ordem=1,
        )
        self.etapa_prova = EtapaCurso.objects.create(
            curso=self.curso,
            titulo="Prova",
            tipo=EtapaCurso.Tipo.PROVA,
            ordem=2,
        )

    def test_operacional_nao_acessa_construtor_de_conteudo(self):
        self.client.force_login(self.operacional)

        resposta = self.client.get(
            reverse("conteudo_curso_operacional", args=(self.curso.id,))
        )

        self.assertEqual(resposta.status_code, 403)

    def test_editor_cria_etapa(self):
        self.client.force_login(self.editor)

        resposta = self.client.post(
            reverse("criar_etapa_operacional", args=(self.curso.id,)),
            {
                "titulo": "Video explicativo",
                "descricao": "Descricao",
                "tipo": EtapaCurso.Tipo.VIDEO,
                "ordem": 3,
                "conteudo": "",
                "video_url": "https://example.com/video",
                "ativo": "on",
            },
            follow=True,
        )
        etapa = EtapaCurso.objects.get(titulo="Video explicativo")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            resposta.redirect_chain[-1][0].split("#")[-1],
            f"etapa-{etapa.id}",
        )
        self.assertContains(resposta, "Video explicativo")
        self.assertTrue(
            EventoAuditoria.objects.filter(
                usuario=self.editor,
                acao=EventoAuditoria.Acao.CADASTRO,
                alvo_tipo="EtapaCurso",
                alvo_repr__contains="Video explicativo",
            ).exists()
        )

    def test_editor_edita_e_alterna_etapa(self):
        self.client.force_login(self.editor)

        resposta = self.client.post(
            reverse("editar_etapa_operacional", args=(self.etapa_texto.id,)),
            {
                "titulo": "Texto atualizado",
                "descricao": "Nova descricao",
                "tipo": EtapaCurso.Tipo.TEXTO,
                "ordem": 1,
                "conteudo": "Conteudo atualizado",
                "video_url": "",
                "ativo": "on",
            },
            follow=True,
        )
        self.etapa_texto.refresh_from_db()

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.etapa_texto.titulo, "Texto atualizado")

        self.client.post(
            reverse("alternar_etapa_operacional", args=(self.etapa_texto.id,)),
            follow=True,
        )
        self.etapa_texto.refresh_from_db()

        self.assertFalse(self.etapa_texto.ativo)

    def test_nao_cria_questao_em_etapa_nao_avaliativa(self):
        self.client.force_login(self.editor)

        resposta = self.client.post(
            reverse("criar_questao_operacional", args=(self.etapa_texto.id,)),
            {
                "enunciado": "Pergunta indevida?",
                "ordem": 1,
            },
            follow=True,
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(
            Questao.objects.filter(
                etapa=self.etapa_texto,
                enunciado="Pergunta indevida?",
            ).exists()
        )

    def test_editor_cria_edita_e_exclui_questao(self):
        self.client.force_login(self.editor)

        resposta_criacao = self.client.post(
            reverse("criar_questao_operacional", args=(self.etapa_prova.id,)),
            {
                "enunciado": "Qual e a resposta?",
                "ordem": 1,
            },
            follow=True,
        )
        questao = Questao.objects.get(etapa=self.etapa_prova)

        self.assertEqual(resposta_criacao.status_code, 200)
        self.assertEqual(
            resposta_criacao.redirect_chain[-1][0].split("#")[-1],
            f"questao-{questao.id}",
        )
        self.assertContains(resposta_criacao, "Qual e a resposta?")

        resposta_edicao = self.client.post(
            reverse("editar_questao_operacional", args=(questao.id,)),
            {
                "enunciado": "Qual e a resposta atualizada?",
                "ordem": 2,
            },
            follow=True,
        )
        questao.refresh_from_db()

        self.assertEqual(resposta_edicao.status_code, 200)
        self.assertEqual(questao.ordem, 2)
        self.assertEqual(questao.enunciado, "Qual e a resposta atualizada?")

        self.client.post(
            reverse("excluir_questao_operacional", args=(questao.id,)),
            follow=True,
        )

        self.assertFalse(Questao.objects.filter(pk=questao.id).exists())
        self.assertTrue(
            EventoAuditoria.objects.filter(
                usuario=self.editor,
                alvo_tipo="Questao",
                detalhes__contains="Questao removida",
            ).exists()
        )

    def test_editor_cria_edita_e_exclui_alternativa(self):
        questao = Questao.objects.create(
            etapa=self.etapa_prova,
            enunciado="Escolha a correta",
        )
        self.client.force_login(self.editor)

        resposta_criacao = self.client.post(
            reverse("criar_alternativa_operacional", args=(questao.id,)),
            {
                "texto": "Alternativa correta",
                "ordem": 1,
                "correta": "on",
            },
            follow=True,
        )
        alternativa = Alternativa.objects.get(questao=questao)

        self.assertEqual(resposta_criacao.status_code, 200)
        self.assertEqual(
            resposta_criacao.redirect_chain[-1][0].split("#")[-1],
            f"questao-{questao.id}",
        )
        self.assertTrue(alternativa.correta)
        self.assertContains(resposta_criacao, "Alternativa correta")

        resposta_edicao = self.client.post(
            reverse("editar_alternativa_operacional", args=(alternativa.id,)),
            {
                "texto": "Alternativa atualizada",
                "ordem": 2,
            },
            follow=True,
        )
        alternativa.refresh_from_db()

        self.assertEqual(resposta_edicao.status_code, 200)
        self.assertEqual(alternativa.texto, "Alternativa atualizada")
        self.assertEqual(alternativa.ordem, 2)
        self.assertFalse(alternativa.correta)

        self.client.post(
            reverse("excluir_alternativa_operacional", args=(alternativa.id,)),
            follow=True,
        )

        self.assertFalse(Alternativa.objects.filter(pk=alternativa.id).exists())
        self.assertTrue(
            EventoAuditoria.objects.filter(
                usuario=self.editor,
                alvo_tipo="Alternativa",
                detalhes__contains="Alternativa removida",
            ).exists()
        )


class OperacaoAdminTest(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(nome="Empresa Operacional")
        self.tecnico = Tecnico.objects.create(
            empresa=self.empresa,
            nome="Técnico Operacional",
            email="operacional@exemplo.com",
            matricula="OP001",
        )
        self.produto = Produto.objects.create(
            nome="Produto Operacional",
            empresa=self.empresa,
        )
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
        self.produto = Produto.objects.create(
            nome="Produto Certificado",
            empresa=self.empresa,
        )
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
            is_superuser=True,
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
        self.produto = Produto.objects.create(
            nome="Produto Relatório",
            empresa=self.empresa,
        )

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
        self.assertEqual(resposta.context["resumo_empresas"][0]["nome"], "Empresa Relatório")
        self.assertEqual(resposta.context["resumo_empresas"][0]["risco"], 3)
        self.assertEqual(resposta.context["resumo_cursos"][0]["risco"], 1)

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

    def test_exporta_relatorio_csv_com_filtros(self):
        self.client.force_login(self.staff)

        resposta = self.client.get(
            reverse("exportar_relatorio_treinamentos"),
            {"situacao": "vencido"},
        )

        conteudo = resposta.content.decode("utf-8-sig")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("text/csv", resposta["Content-Type"])
        self.assertIn("Empresa;Tecnico;Matricula;Produto;Curso;Situacao", conteudo)
        self.assertIn("Curso Vencido", conteudo)
        self.assertNotIn("Curso Pendente", conteudo)


class LiberarCursoLoteTest(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="admin-liberacao",
            password="SenhaForte123!",
            is_staff=True,
            is_superuser=True,
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
        self.produto = Produto.objects.create(
            nome="Produto Liberação",
            empresa=self.empresa,
        )
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

    def test_liberacao_lote_rejeita_curso_fora_da_empresa(self):
        produto_fora = Produto.objects.create(
            nome="Produto Fora",
            empresa=self.outra_empresa,
        )
        curso_fora = Curso.objects.create(nome="Curso Fora", produto=produto_fora)
        self.client.force_login(self.staff)

        resposta = self.client.post(
            reverse("liberar_curso_lote"),
            {
                "empresa": self.empresa.id,
                "curso": curso_fora.id,
                "todos_tecnicos": "on",
                "obrigatorio": "on",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(
            CursoLiberado.objects.filter(
                tecnico=self.tecnico_1,
                curso=curso_fora,
            ).exists()
        )
        self.assertContains(resposta, "Faça uma escolha válida", html=False)

    def test_importa_liberacoes_por_csv(self):
        self.client.force_login(self.staff)
        arquivo = SimpleUploadedFile(
            "liberacoes.csv",
            (
                "matricula,email,obrigatorio\n"
                "LIB001,,sim\n"
                ",tecnico2@exemplo.com,nao\n"
            ).encode(),
            content_type="text/csv",
        )

        resposta = self.client.post(
            reverse("importar_liberacoes_operacionais"),
            {
                "empresa": self.empresa.id,
                "curso": self.curso.id,
                "arquivo": arquivo,
                "obrigatorio": "on",
            },
            follow=True,
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
                obrigatorio=False,
                ativo=True,
            ).exists()
        )

    @override_settings(MAX_CSV_IMPORT_SIZE_BYTES=10)
    def test_importacao_liberacoes_rejeita_csv_acima_do_limite(self):
        self.client.force_login(self.staff)
        arquivo = SimpleUploadedFile(
            "liberacoes.csv",
            "matricula,email,obrigatorio\nLIB001,,sim\n".encode(),
            content_type="text/csv",
        )

        resposta = self.client.post(
            reverse("importar_liberacoes_operacionais"),
            {
                "empresa": self.empresa.id,
                "curso": self.curso.id,
                "arquivo": arquivo,
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Arquivo CSV muito grande")
        self.assertFalse(
            CursoLiberado.objects.filter(
                tecnico=self.tecnico_1,
                curso=self.curso,
            ).exists()
        )

    def test_importacao_liberacoes_reativa_e_atualiza_existente(self):
        CursoLiberado.objects.create(
            tecnico=self.tecnico_1,
            curso=self.curso,
            obrigatorio=False,
            ativo=False,
        )
        self.client.force_login(self.staff)
        arquivo = SimpleUploadedFile(
            "liberacoes.csv",
            "matricula,email,obrigatorio\nLIB001,,sim\n".encode(),
            content_type="text/csv",
        )

        resposta = self.client.post(
            reverse("importar_liberacoes_operacionais"),
            {
                "empresa": self.empresa.id,
                "curso": self.curso.id,
                "arquivo": arquivo,
            },
            follow=True,
        )

        liberacao = CursoLiberado.objects.get(tecnico=self.tecnico_1, curso=self.curso)
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(liberacao.ativo)
        self.assertTrue(liberacao.obrigatorio)

    def test_importacao_liberacoes_rejeita_empresa_fora_do_escopo(self):
        responsavel = User.objects.create_user(
            username="responsavel-liberacao",
            password="SenhaForte123!",
            is_staff=True,
        )
        ResponsavelEmpresa.objects.create(
            empresa=self.empresa,
            usuario=responsavel,
            papel=ResponsavelEmpresa.Papel.OPERACIONAL,
        )
        self.client.force_login(responsavel)
        arquivo = SimpleUploadedFile(
            "liberacoes.csv",
            "matricula,email\nLIB004,\n".encode(),
            content_type="text/csv",
        )

        resposta = self.client.post(
            reverse("importar_liberacoes_operacionais"),
            {
                "empresa": self.outra_empresa.id,
                "curso": self.curso.id,
                "arquivo": arquivo,
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(
            CursoLiberado.objects.filter(
                tecnico=self.tecnico_outra_empresa,
                curso=self.curso,
            ).exists()
        )
        self.assertContains(resposta, "Faça uma escolha válida", html=False)

    def test_importacao_liberacoes_com_erro_nao_grava_linhas_validas(self):
        self.client.force_login(self.staff)
        arquivo = SimpleUploadedFile(
            "liberacoes.csv",
            (
                "matricula,email\n"
                "LIB001,\n"
                "INEXISTENTE,\n"
            ).encode(),
            content_type="text/csv",
        )

        resposta = self.client.post(
            reverse("importar_liberacoes_operacionais"),
            {
                "empresa": self.empresa.id,
                "curso": self.curso.id,
                "arquivo": arquivo,
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Linha 3: tecnico nao encontrado.")
        self.assertFalse(
            CursoLiberado.objects.filter(tecnico=self.tecnico_1, curso=self.curso).exists()
        )


class EscopoEmpresaTest(TestCase):
    def setUp(self):
        self.empresa_a = Empresa.objects.create(nome="Empresa A")
        self.empresa_b = Empresa.objects.create(nome="Empresa B")
        self.responsavel = User.objects.create_user(
            username="responsavel-a",
            password="SenhaForte123!",
            is_staff=True,
        )
        ResponsavelEmpresa.objects.create(
            empresa=self.empresa_a,
            usuario=self.responsavel,
            papel=ResponsavelEmpresa.Papel.OPERACIONAL,
        )
        self.superadmin = User.objects.create_user(
            username="superadmin",
            password="SenhaForte123!",
            is_staff=True,
            is_superuser=True,
        )
        self.tecnico_a = Tecnico.objects.create(
            empresa=self.empresa_a,
            nome="TÃ©cnico Empresa A",
            email="tecnico.a@exemplo.com",
            matricula="ESCOPO-A",
        )
        self.tecnico_b = Tecnico.objects.create(
            empresa=self.empresa_b,
            nome="TÃ©cnico Empresa B",
            email="tecnico.b@exemplo.com",
            matricula="ESCOPO-B",
        )
        self.produto_a = Produto.objects.create(
            nome="Produto Escopo A",
            empresa=self.empresa_a,
        )
        self.produto_b = Produto.objects.create(
            nome="Produto Escopo B",
            empresa=self.empresa_b,
        )
        self.curso_a = Curso.objects.create(nome="Curso Empresa A", produto=self.produto_a)
        self.curso_b = Curso.objects.create(nome="Curso Empresa B", produto=self.produto_b)
        self.liberacao_a = CursoLiberado.objects.create(
            tecnico=self.tecnico_a,
            curso=self.curso_a,
        )
        self.liberacao_b = CursoLiberado.objects.create(
            tecnico=self.tecnico_b,
            curso=self.curso_b,
        )
        self.conclusao_a = ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico_a,
            curso=self.curso_a,
            data_conclusao=timezone.localdate(),
        )
        self.conclusao_b = ConclusaoTreinamento.objects.create(
            tecnico=self.tecnico_b,
            curso=self.curso_b,
            data_conclusao=timezone.localdate(),
        )
        self.site = AdminSite()

    def test_responsavel_ve_no_relatorio_apenas_sua_empresa(self):
        self.client.force_login(self.responsavel)

        resposta = self.client.get(reverse("relatorio_treinamentos"))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Curso Empresa A")
        self.assertNotContains(resposta, "Curso Empresa B")
        self.assertEqual(resposta.context["totais"]["total"], 1)
        self.assertQuerySetEqual(
            resposta.context["empresas"],
            [self.empresa_a],
            transform=lambda empresa: empresa,
        )

    def test_responsavel_nao_forca_filtro_para_empresa_fora_do_escopo(self):
        self.client.force_login(self.responsavel)

        resposta = self.client.get(
            reverse("relatorio_treinamentos"),
            {"empresa": str(self.empresa_b.id)},
        )

        self.assertEqual(resposta.context["totais"]["total"], 1)
        self.assertContains(resposta, "Curso Empresa A")
        self.assertNotContains(resposta, "Curso Empresa B")

    def test_responsavel_exporta_csv_apenas_da_sua_empresa(self):
        self.client.force_login(self.responsavel)

        resposta = self.client.get(reverse("exportar_relatorio_treinamentos"))

        conteudo = resposta.content.decode("utf-8-sig")
        self.assertEqual(resposta.status_code, 200)
        self.assertIn("Curso Empresa A", conteudo)
        self.assertNotIn("Curso Empresa B", conteudo)

    def test_superadmin_mantem_visao_global_no_relatorio(self):
        self.client.force_login(self.superadmin)

        resposta = self.client.get(reverse("relatorio_treinamentos"))

        self.assertEqual(resposta.context["totais"]["total"], 2)
        self.assertContains(resposta, "Curso Empresa A")
        self.assertContains(resposta, "Curso Empresa B")

    def test_liberacao_lote_limita_empresas_e_tecnicos_do_responsavel(self):
        self.client.force_login(self.responsavel)

        resposta = self.client.get(reverse("liberar_curso_lote"))
        form = resposta.context["form"]

        self.assertQuerySetEqual(
            form.fields["empresa"].queryset,
            [self.empresa_a],
            transform=lambda empresa: empresa,
        )
        self.assertIn(self.tecnico_a, form.fields["tecnicos"].queryset)
        self.assertNotIn(self.tecnico_b, form.fields["tecnicos"].queryset)
        self.assertIn(self.curso_a, form.fields["curso"].queryset)
        self.assertNotIn(self.curso_b, form.fields["curso"].queryset)

    def test_liberacao_lote_rejeita_empresa_fora_do_escopo_do_responsavel(self):
        curso_novo = Curso.objects.create(nome="Curso Novo", produto=self.produto_b)
        self.client.force_login(self.responsavel)

        resposta = self.client.post(
            reverse("liberar_curso_lote"),
            {
                "empresa": self.empresa_b.id,
                "curso": curso_novo.id,
                "todos_tecnicos": "on",
                "obrigatorio": "on",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(
            CursoLiberado.objects.filter(
                tecnico=self.tecnico_b,
                curso=curso_novo,
            ).exists()
        )

    def test_admin_limita_dados_operacionais_por_empresa(self):
        request = RequestFactory().get("/admin/core/tecnico/")
        request.user = self.responsavel

        admin_empresa = EmpresaAdmin(Empresa, self.site)
        admin_tecnico = TecnicoAdmin(Tecnico, self.site)
        admin_liberacao = CursoLiberadoAdmin(CursoLiberado, self.site)
        admin_conclusao = ConclusaoTreinamentoAdmin(
            ConclusaoTreinamento,
            self.site,
        )

        self.assertIn(self.empresa_a, admin_empresa.get_queryset(request))
        self.assertNotIn(self.empresa_b, admin_empresa.get_queryset(request))
        self.assertIn(self.tecnico_a, admin_tecnico.get_queryset(request))
        self.assertNotIn(self.tecnico_b, admin_tecnico.get_queryset(request))
        self.assertIn(self.liberacao_a, admin_liberacao.get_queryset(request))
        self.assertNotIn(self.liberacao_b, admin_liberacao.get_queryset(request))
        self.assertIn(self.conclusao_a, admin_conclusao.get_queryset(request))
        self.assertNotIn(self.conclusao_b, admin_conclusao.get_queryset(request))

    def test_superadmin_mantem_visao_global_no_admin(self):
        request = RequestFactory().get("/admin/core/tecnico/")
        request.user = self.superadmin

        admin_tecnico = TecnicoAdmin(Tecnico, self.site)

        self.assertIn(self.tecnico_a, admin_tecnico.get_queryset(request))
        self.assertIn(self.tecnico_b, admin_tecnico.get_queryset(request))
