from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    Alternativa,
    Curso,
    CursoLiberado,
    Empresa,
    EtapaCurso,
    Produto,
    Questao,
    ResponsavelEmpresa,
    Tecnico,
)


EMPRESAS = ["Concessionaria", "Condominio", "Dtive", "Estacione", "Abastece"]
CURSO_NOME = "Boas praticas de atendimento - SLT"
PRODUTO_NOME = "SLT"
VIDEO_URL = "https://www.youtube.com/embed/I8XUaERv_wg"
PDF_RELATIVO = "cursos/pdfs/boas_praticas_atendimento_slt.pdf"


PDF_PAGINAS = [
    [
        "Boas praticas de atendimento - SLT",
        "",
        "Objetivo do curso",
        "Capacitar tecnicos para realizar atendimentos de manutencao com postura profissional,",
        "comunicacao clara, seguranca operacional e registro adequado das atividades.",
        "",
        "Publico-alvo",
        "Tecnicos de campo que atendem empresas do grupo com produto SLT.",
        "",
        "Resultado esperado",
        "Ao final, o tecnico deve saber preparar o atendimento, comunicar riscos, executar",
        "a intervencao com qualidade e encerrar o chamado com evidencias confiaveis.",
    ],
    [
        "1. Preparacao antes do atendimento",
        "",
        "- Confirme empresa, local, responsavel e janela de atendimento.",
        "- Verifique historico do equipamento, chamados anteriores e escopo autorizado.",
        "- Separe ferramentas, EPIs e materiais antes do deslocamento.",
        "- Avise atrasos ou impedimentos assim que forem identificados.",
        "",
        "Boa pratica central:",
        "Nunca inicie uma atividade sem entender o impacto operacional e sem alinhar com o",
        "responsavel local.",
    ],
    [
        "2. Conduta no local",
        "",
        "- Apresente-se de forma clara e confirme a solicitacao antes de atuar.",
        "- Use linguagem simples, objetiva e respeitosa.",
        "- Isole a area quando houver risco para pessoas, veiculos ou equipamentos.",
        "- Explique o que sera feito, o tempo estimado e possiveis impactos.",
        "- Evite improvisos que comprometam seguranca, garantia ou padrao tecnico.",
    ],
    [
        "3. Comunicacao e registro",
        "",
        "- Registre inicio, diagnostico, acao executada, pecas utilizadas e resultado.",
        "- Inclua fotos ou evidencias quando aplicavel.",
        "- Informe pendencias, restricoes e proximos passos.",
        "- Se o problema nao for resolvido, deixe claro o motivo e o plano de continuidade.",
        "",
        "Encerramento adequado:",
        "O atendimento termina quando o responsavel entende o que foi feito e o chamado possui",
        "informacoes suficientes para auditoria e acompanhamento.",
    ],
    [
        "Checklist rapido do tecnico SLT",
        "",
        "[ ] Chamado e empresa conferidos",
        "[ ] Responsavel local identificado",
        "[ ] EPI e ferramentas verificados",
        "[ ] Riscos comunicados",
        "[ ] Area protegida quando necessario",
        "[ ] Teste funcional realizado",
        "[ ] Evidencias registradas",
        "[ ] Responsavel local orientado",
        "[ ] Chamado encerrado com informacoes completas",
    ],
]


CONTEUDO_TEXTO = """Este curso apresenta um roteiro pratico para atendimento tecnico do produto SLT.

O tecnico deve atuar com foco em quatro pilares:
1. Preparacao antes do atendimento.
2. Comunicacao clara com o responsavel local.
3. Execucao segura e organizada.
4. Registro completo das evidencias e encerramento do chamado.

Antes de iniciar qualquer atividade, confirme a empresa atendida, o local, o responsavel, o escopo do chamado e as condicoes de seguranca. Durante a execucao, comunique riscos, use EPI quando necessario, evite improvisos e registre qualquer desvio encontrado.

Ao encerrar, informe o que foi feito, qual foi o resultado, se ha pendencias e quais proximos passos devem ser acompanhados."""


CHECKLIST = """Checklist de atendimento SLT:

- Confirmar empresa, local e responsavel.
- Conferir escopo do chamado e historico disponivel.
- Preparar ferramentas, EPI e materiais.
- Comunicar impacto operacional antes de intervir.
- Isolar a area se houver risco.
- Executar a manutencao conforme procedimento.
- Testar o funcionamento antes de encerrar.
- Registrar diagnostico, acao, evidencias e pendencias.
- Orientar o responsavel local e finalizar o chamado."""


TESTE_QUESTOES = [
    (
        "Antes de iniciar o atendimento, qual atitude e mais adequada?",
        [
            ("Confirmar empresa, local, responsavel e escopo do chamado.", True),
            ("Comecar a manutencao imediatamente para ganhar tempo.", False),
            ("Ignorar o historico do equipamento.", False),
            ("Aguardar apenas o tecnico lider chegar, sem verificar nada.", False),
        ],
    ),
    (
        "Durante o atendimento, como o tecnico deve comunicar um risco operacional?",
        [
            (
                "De forma clara, objetiva e antes de executar a acao que pode gerar impacto.",
                True,
            ),
            ("Somente depois de terminar o servico.", False),
            ("Apenas se o cliente perguntar.", False),
            ("Usando termos tecnicos complexos para evitar questionamentos.", False),
        ],
    ),
    (
        "Qual item torna o encerramento do chamado mais confiavel?",
        [
            ("Registro de diagnostico, acao executada, resultado e evidencias.", True),
            ("Apenas informar verbalmente que esta tudo certo.", False),
            ("Fechar o chamado sem teste funcional.", False),
            ("Registrar somente o horario de chegada.", False),
        ],
    ),
]


PROVA_QUESTOES = [
    (
        "Um tecnico chega ao local e percebe que a manutencao pode interromper a operacao. O que deve fazer?",
        [
            ("Alinhar o impacto com o responsavel local antes de intervir.", True),
            ("Executar mesmo assim para cumprir prazo.", False),
            ("Encerrar o chamado como improdutivo sem explicar.", False),
            ("Pedir que outro tecnico decida depois.", False),
        ],
    ),
    (
        "Qual conduta representa melhor uma boa pratica de atendimento?",
        [
            (
                "Ser pontual, explicar o procedimento, executar com seguranca e registrar evidencias.",
                True,
            ),
            ("Falar pouco, evitar perguntas e finalizar rapido.", False),
            ("Resolver por tentativa e erro sem registrar.", False),
            ("Priorizar velocidade acima da seguranca.", False),
        ],
    ),
    (
        "Se o problema nao puder ser resolvido no primeiro atendimento, o tecnico deve:",
        [
            ("Registrar motivo, pendencias, riscos e proximos passos.", True),
            ("Apagar as evidencias para evitar cobrancas.", False),
            ("Informar apenas que precisa voltar outro dia.", False),
            ("Deixar o chamado aberto sem comentarios.", False),
        ],
    ),
    (
        "Por que o registro de fotos ou evidencias pode ser importante?",
        [
            ("Porque ajuda auditoria, acompanhamento e comprovacao da execucao.", True),
            ("Porque substitui todos os testes tecnicos.", False),
            ("Porque elimina a necessidade de comunicar o cliente.", False),
            ("Porque permite encerrar chamado sem descricao.", False),
        ],
    ),
    (
        "Qual e o melhor criterio para considerar o atendimento encerrado?",
        [
            (
                "Servico testado, responsavel orientado e chamado registrado com informacoes completas.",
                True,
            ),
            ("Tecnico saiu do local.", False),
            ("Horario planejado terminou.", False),
            ("Foi enviada uma mensagem curta dizendo concluido.", False),
        ],
    ),
]


def escapar_pdf(texto):
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def criar_pdf(caminho):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    objetos = []
    paginas_refs = []
    for pagina in PDF_PAGINAS:
        linhas = ["BT", "/F1 12 Tf", "50 790 Td", "16 TL"]
        primeira = True
        for linha in pagina:
            if primeira:
                linhas.append(f"({escapar_pdf(linha)}) Tj")
                primeira = False
            else:
                linhas.append(f"T* ({escapar_pdf(linha)}) Tj")
        linhas.append("ET")
        stream = "\n".join(linhas).encode("latin-1", errors="replace")
        conteudo_id = len(objetos) + 1
        objetos.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
        pagina_id = len(objetos) + 1
        paginas_refs.append(pagina_id)
        objetos.append(
            f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 0 0 R >> >> /Contents {conteudo_id} 0 R >>"
        .encode("ascii"))

    fonte_id = len(objetos) + 1
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    paginas_id = len(objetos) + 1
    kids = " ".join(f"{ref} 0 R" for ref in paginas_refs)
    objetos.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(paginas_refs)} >>".encode("ascii"))
    catalogo_id = len(objetos) + 1
    objetos.append(f"<< /Type /Catalog /Pages {paginas_id} 0 R >>".encode("ascii"))

    corrigidos = [
        obj.replace(b"/Parent 0 0 R", f"/Parent {paginas_id} 0 R".encode("ascii"))
        .replace(b"/F1 0 0 R", f"/F1 {fonte_id} 0 R".encode("ascii"))
        for obj in objetos
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for indice, obj in enumerate(corrigidos, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{indice} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(corrigidos) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(corrigidos) + 1} /Root {catalogo_id} 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    caminho.write_bytes(pdf)


class Command(BaseCommand):
    help = "Cria a base de teste SLT multiempresa com usuarios, curso completo e liberacoes."

    def add_arguments(self, parser):
        parser.add_argument("--senha-responsavel", default="resp@123")
        parser.add_argument("--senha-editor", default="ed@123")
        parser.add_argument("--senha-tecnico", default="tec@123")
        parser.add_argument(
            "--reset-curso",
            action="store_true",
            help="Remove etapas/questoes do curso SLT antes de recria-lo.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        responsavel = self._usuario(
            User,
            "Responsavel_teste",
            "responsavel_teste@teste.local",
            options["senha_responsavel"],
            is_staff=True,
        )
        editor = self._usuario(
            User,
            "Editor_teste",
            "editor_teste@teste.local",
            options["senha_editor"],
            is_staff=True,
        )
        usuario_tecnico = self._usuario(
            User,
            "Tecnico_teste",
            "tecnico_teste@teste.local",
            options["senha_tecnico"],
            is_staff=False,
        )

        pdf_absoluto = Path(settings.MEDIA_ROOT) / PDF_RELATIVO
        criar_pdf(pdf_absoluto)

        empresas = [self._empresa(nome) for nome in EMPRESAS]
        cursos = 0
        liberacoes = 0
        for indice, empresa in enumerate(empresas):
            produto = self._produto(empresa)
            tecnico = self._tecnico(empresa, usuario_tecnico, indice)
            self._responsavel(empresa, responsavel, ResponsavelEmpresa.Papel.OPERACIONAL)
            self._responsavel(empresa, editor, ResponsavelEmpresa.Papel.EDITOR_CURSOS)
            curso = self._curso(produto, reset=options["reset_curso"])
            CursoLiberado.objects.update_or_create(
                tecnico=tecnico,
                curso=curso,
                defaults={"obrigatorio": True, "ativo": True},
            )
            cursos += 1
            liberacoes += 1

        self.stdout.write(self.style.SUCCESS("Base de teste SLT criada/atualizada."))
        self.stdout.write(f"Empresas: {len(empresas)}")
        self.stdout.write(f"Cursos: {cursos}")
        self.stdout.write(f"Liberacoes para Tecnico_teste: {liberacoes}")
        self.stdout.write(f"PDF: {pdf_absoluto}")
        self.stdout.write("Acessos:")
        self.stdout.write("  Responsavel_teste / " + options["senha_responsavel"])
        self.stdout.write("  Editor_teste / " + options["senha_editor"])
        self.stdout.write("  Tecnico_teste / " + options["senha_tecnico"])

    def _usuario(self, User, username, email, senha, is_staff):
        usuario, _ = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": username,
                "is_staff": is_staff,
                "is_active": True,
            },
        )
        usuario.email = email
        usuario.first_name = username
        usuario.is_staff = is_staff
        usuario.is_active = True
        usuario.set_password(senha)
        usuario.save()
        return usuario

    def _empresa(self, nome):
        empresa, _ = Empresa.objects.update_or_create(
            nome=nome,
            defaults={
                "responsavel": "Responsavel_teste",
                "email": f"contato.{nome.lower()}@teste.local",
                "ativa": True,
            },
        )
        return empresa

    def _produto(self, empresa):
        produto, _ = Produto.objects.update_or_create(
            empresa=empresa,
            nome=PRODUTO_NOME,
            defaults={
                "descricao": "Produto SLT para testes operacionais.",
                "ativo": True,
            },
        )
        return produto

    def _responsavel(self, empresa, usuario, papel):
        ResponsavelEmpresa.objects.update_or_create(
            empresa=empresa,
            usuario=usuario,
            papel=papel,
            defaults={"ativo": True},
        )

    def _tecnico(self, empresa, usuario, indice):
        principal = indice == 0
        email = "tecnico_teste@teste.local"
        matricula = "TECNICO_TESTE"
        if not principal:
            email = f"tecnico_teste+empresa-{empresa.id}@teste.local"
            matricula = f"TECNICO_TESTE-E{empresa.id}"[:50]
        tecnico, _ = Tecnico.objects.update_or_create(
            matricula=matricula,
            defaults={
                "empresa": empresa,
                "usuario": usuario,
                "nome": "Tecnico_teste",
                "email": email,
                "telefone": "",
                "equipe": "Teste",
                "regiao": "Teste",
                "ativo": True,
            },
        )
        return tecnico

    def _curso(self, produto, reset):
        curso, _ = Curso.objects.update_or_create(
            produto=produto,
            nome=CURSO_NOME,
            defaults={
                "descricao": (
                    "Curso completo de teste para validar video, texto, PDF, "
                    "teste de conhecimento, prova final, liberacao e certificado no produto SLT."
                ),
                "validade_meses": 12,
                "nota_minima": 70,
                "link_notebooklm": "",
                "material_pdf": PDF_RELATIVO,
                "ativo": True,
            },
        )
        if reset:
            curso.etapas.all().delete()
        if curso.etapas.exists():
            return curso

        EtapaCurso.objects.create(
            curso=curso,
            titulo="Boas-vindas e objetivos do atendimento SLT",
            descricao="Visao geral do que sera avaliado no curso.",
            tipo=EtapaCurso.Tipo.TEXTO,
            ordem=1,
            conteudo=CONTEUDO_TEXTO,
            ativo=True,
        )
        EtapaCurso.objects.create(
            curso=curso,
            titulo="Video de referencia para atendimento",
            descricao="Assista ao video indicado para contextualizar postura, comunicacao e organizacao do atendimento.",
            tipo=EtapaCurso.Tipo.VIDEO,
            ordem=2,
            video_url=VIDEO_URL,
            conteudo=(
                "Assista ao video e observe como comunicacao, clareza e postura "
                "influenciam a experiencia de atendimento."
            ),
            ativo=True,
        )
        EtapaCurso.objects.create(
            curso=curso,
            titulo="Checklist operacional do tecnico",
            descricao="Resumo pratico para usar antes, durante e depois do atendimento.",
            tipo=EtapaCurso.Tipo.TEXTO,
            ordem=3,
            conteudo=CHECKLIST,
            ativo=True,
        )
        etapa_teste = EtapaCurso.objects.create(
            curso=curso,
            titulo="Teste de conhecimento",
            descricao="Valide se os principais conceitos foram compreendidos.",
            tipo=EtapaCurso.Tipo.TESTE,
            ordem=4,
            conteudo="Responda as questoes para revisar os pontos essenciais antes da prova final.",
            ativo=True,
        )
        self._questoes(etapa_teste, TESTE_QUESTOES)
        etapa_prova = EtapaCurso.objects.create(
            curso=curso,
            titulo="Prova final",
            descricao="Avaliacao final para conclusao do curso.",
            tipo=EtapaCurso.Tipo.PROVA,
            ordem=5,
            conteudo="Responda todas as questoes. A nota minima do curso e 70%.",
            ativo=True,
        )
        self._questoes(etapa_prova, PROVA_QUESTOES)
        return curso

    def _questoes(self, etapa, questoes):
        for indice, (enunciado, alternativas) in enumerate(questoes, start=1):
            questao = Questao.objects.create(
                etapa=etapa,
                enunciado=enunciado,
                ordem=indice,
            )
            for ordem, (texto, correta) in enumerate(alternativas, start=1):
                Alternativa.objects.create(
                    questao=questao,
                    texto=texto,
                    correta=correta,
                    ordem=ordem,
                )
