from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    Alternativa,
    ConclusaoTreinamento,
    Curso,
    CursoLiberado,
    EtapaCurso,
    Produto,
    ProgressoCurso,
    Questao,
    Tecnico,
    TentativaAvaliacao,
)


VIDEO_DEMO_1 = "https://www.youtube.com/embed/PD-MdiUm1_Y"
VIDEO_DEMO_2 = "https://www.youtube.com/embed/PD-MdiUm1_Y"


CURSOS = [
    {
        "produto": "Abastece",
        "descricao_produto": (
            "Capacitação para instalação, manutenção e suporte aos sistemas de "
            "identificação e pagamento em postos de combustíveis."
        ),
        "curso": "Fundamentos técnicos do Abastece",
        "descricao_curso": (
            "Trilha demonstrativa sobre segurança, diagnóstico e atendimento "
            "técnico em uma solução de pagamento para abastecimento."
        ),
        "contexto": "pista de abastecimento",
        "equipamento": "terminal de pagamento e seus periféricos",
        "risco": "fontes de ignição, circulação de veículos e exposição a combustível",
        "verificacao": "alimentação, comunicação, conectores e estado físico do terminal",
        "acao_segura": "isolar a área e seguir os procedimentos de segurança do posto",
    },
    {
        "produto": "Drive",
        "descricao_produto": (
            "Capacitação para instalação, manutenção e suporte aos sistemas de "
            "identificação e pagamento em operações de drive-thru."
        ),
        "curso": "Operação e suporte técnico do Drive",
        "descricao_curso": (
            "Trilha demonstrativa para diagnóstico organizado, atendimento e "
            "restabelecimento seguro da operação em drive-thrus."
        ),
        "contexto": "faixa de atendimento do drive-thru",
        "equipamento": "leitor, terminal de operação e conexão de rede",
        "risco": "movimentação contínua de veículos e interrupção da fila",
        "verificacao": "energia, rede, posicionamento dos leitores e resposta do sistema",
        "acao_segura": "sinalizar a faixa e alinhar a intervenção com o responsável da loja",
    },
    {
        "produto": "Estacione",
        "descricao_produto": (
            "Capacitação para instalação, manutenção e suporte aos sistemas de "
            "identificação e pagamento em estacionamentos."
        ),
        "curso": "Diagnóstico técnico do Estacione",
        "descricao_curso": (
            "Trilha demonstrativa sobre segurança em cancelas, análise de falhas e "
            "validação de entrada e saída de veículos."
        ),
        "contexto": "pista de entrada e saída do estacionamento",
        "equipamento": "cancela, leitor, sensor de presença e totem",
        "risco": "movimento mecânico da cancela e circulação de veículos",
        "verificacao": "sensores, laços, alimentação, comunicação e mecanismo da cancela",
        "acao_segura": "bloquear o acionamento e sinalizar a pista antes da intervenção",
    },
    {
        "produto": "Condomínio",
        "descricao_produto": (
            "Capacitação para instalação, manutenção e suporte aos sistemas de "
            "identificação e controle de acesso em condomínios."
        ),
        "curso": "Controle de acesso no Condomínio",
        "descricao_curso": (
            "Trilha demonstrativa para atendimento técnico seguro em portarias, "
            "leitores, controladoras e dispositivos de acesso."
        ),
        "contexto": "acesso veicular e portaria do condomínio",
        "equipamento": "controladora, leitor, acionamento e sensores de segurança",
        "risco": "acesso indevido, aprisionamento e movimentação do portão",
        "verificacao": "alimentação, eventos da controladora, sensores e comunicação",
        "acao_segura": "combinar o bloqueio do acesso com a portaria e preservar uma rota segura",
    },
]


class Command(BaseCommand):
    help = "Apaga os dados de negócio atuais e cria quatro cursos demonstrativos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sem-tecnico",
            action="store_true",
            help="Cria somente produtos e cursos, sem usuário técnico demonstrativo.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self._limpar_dados()
        tecnico = None if options["sem_tecnico"] else self._criar_tecnico()

        totais = {"cursos": 0, "etapas": 0, "questoes": 0}
        for dados in CURSOS:
            curso = self._criar_curso(dados)
            if tecnico:
                CursoLiberado.objects.create(
                    tecnico=tecnico, curso=curso, obrigatorio=True, ativo=True
                )
            totais["cursos"] += 1
            totais["etapas"] += curso.etapas.count()
            totais["questoes"] += Questao.objects.filter(etapa__curso=curso).count()

        self.stdout.write(
            self.style.SUCCESS(
                "Base demonstrativa criada: "
                f"{totais['cursos']} cursos, {totais['etapas']} etapas e "
                f"{totais['questoes']} questões."
            )
        )
        if tecnico:
            self.stdout.write("Técnico: tecnico.demo@semparar.com.br")
            self.stdout.write("Senha: Demo@12345")
        else:
            self.stdout.write(
                "Nenhum técnico foi criado. Cadastre os técnicos reais pelo admin."
            )

    def _limpar_dados(self):
        User = get_user_model()
        TentativaAvaliacao.objects.all().delete()
        ProgressoCurso.objects.all().delete()
        ConclusaoTreinamento.objects.all().delete()
        CursoLiberado.objects.all().delete()
        Curso.objects.all().delete()
        Produto.objects.all().delete()
        Tecnico.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

    def _criar_tecnico(self):
        User = get_user_model()
        usuario = User.objects.create_user(
            username="tecnico.demo@semparar.com.br",
            email="tecnico.demo@semparar.com.br",
            password="Demo@12345",
            first_name="Técnico",
            last_name="Demonstração",
        )
        return Tecnico.objects.create(
            usuario=usuario,
            nome="Técnico Demonstração",
            email=usuario.email,
            matricula="DEMO-001",
            telefone="(11) 99999-0000",
            equipe="Validação da plataforma",
            regiao="São Paulo",
            ativo=True,
        )

    def _criar_curso(self, dados):
        produto = Produto.objects.create(
            nome=dados["produto"],
            descricao=dados["descricao_produto"],
            ativo=True,
        )
        curso = Curso.objects.create(
            nome=dados["curso"],
            descricao=dados["descricao_curso"],
            produto=produto,
            validade_meses=6,
            nota_minima=70,
            ativo=True,
        )

        EtapaCurso.objects.create(
            curso=curso,
            ordem=1,
            tipo=EtapaCurso.Tipo.VIDEO,
            titulo="Boas-vindas e visão geral",
            descricao=(
                "Conheça os objetivos da trilha e a postura esperada durante um "
                f"atendimento na {dados['contexto']}."
            ),
            video_url=VIDEO_DEMO_1,
            conteudo=(
                "Vídeo demonstrativo usado apenas para validar a reprodução na "
                "plataforma. O conteúdo técnico oficial deverá substituir este material."
            ),
        )
        EtapaCurso.objects.create(
            curso=curso,
            ordem=2,
            tipo=EtapaCurso.Tipo.TEXTO,
            titulo="Segurança e preparação do atendimento",
            descricao="Planejamento antes de tocar no equipamento.",
            conteudo=self._texto_seguranca(dados),
        )
        EtapaCurso.objects.create(
            curso=curso,
            ordem=3,
            tipo=EtapaCurso.Tipo.VIDEO,
            titulo="Diagnóstico técnico guiado",
            descricao="Demonstração da sequência lógica de diagnóstico.",
            video_url=VIDEO_DEMO_2,
            conteudo=(
                "Este vídeo é uma mídia de demonstração. Na versão oficial, grave o "
                f"procedimento de inspeção de {dados['equipamento']}."
            ),
        )
        EtapaCurso.objects.create(
            curso=curso,
            ordem=4,
            tipo=EtapaCurso.Tipo.TEXTO,
            titulo="Diagnóstico, registro e encerramento",
            descricao="Como investigar a falha e documentar o serviço.",
            conteudo=self._texto_diagnostico(dados),
        )

        teste = EtapaCurso.objects.create(
            curso=curso,
            ordem=5,
            tipo=EtapaCurso.Tipo.TESTE,
            titulo="Teste de fixação",
            descricao="Verifique seu entendimento antes da prova final.",
        )
        self._criar_questoes(
            teste,
            [
                (
                    "Qual deve ser a primeira atitude antes de iniciar a intervenção?",
                    dados["acao_segura"].capitalize() + ".",
                    [
                        "Reiniciar todos os equipamentos sem avisar o cliente.",
                        "Trocar componentes antes de confirmar o sintoma.",
                        "Desativar os registros para acelerar o atendimento.",
                    ],
                ),
                (
                    "Qual abordagem produz um diagnóstico mais confiável?",
                    "Confirmar o sintoma, coletar evidências e testar uma hipótese por vez.",
                    [
                        "Alterar várias configurações simultaneamente.",
                        "Considerar apenas o relato e dispensar testes.",
                        "Substituir o conjunto completo em toda ocorrência.",
                    ],
                ),
                (
                    "O que deve constar no encerramento do atendimento?",
                    "Sintoma, causa identificada, ação executada e validação final.",
                    [
                        "Somente o horário de chegada do técnico.",
                        "Apenas o nome do equipamento atendido.",
                        "Somente uma fotografia sem descrição.",
                    ],
                ),
            ],
        )

        prova = EtapaCurso.objects.create(
            curso=curso,
            ordem=6,
            tipo=EtapaCurso.Tipo.PROVA,
            titulo="Prova final de certificação",
            descricao=(
                "É necessário atingir pelo menos 70%. Em caso de reprovação, toda "
                "a trilha deverá ser refeita."
            ),
        )
        self._criar_questoes(
            prova,
            [
                (
                    f"Qual risco merece atenção especial na {dados['contexto']}?",
                    dados["risco"].capitalize() + ".",
                    [
                        "Somente a disponibilidade de material de escritório.",
                        "A cor externa do equipamento.",
                        "O tempo de uso do uniforme.",
                    ],
                ),
                (
                    "Qual conjunto representa uma verificação inicial adequada?",
                    dados["verificacao"].capitalize() + ".",
                    [
                        "Apenas a limpeza externa do local.",
                        "Somente a versão do navegador do cliente.",
                        "Troca imediata de todas as peças.",
                    ],
                ),
                (
                    "Ao não reproduzir a falha, o técnico deve:",
                    "Registrar as evidências, condições do teste e orientar o monitoramento.",
                    [
                        "Inventar uma causa provável para fechar a ordem.",
                        "Marcar o equipamento como condenado.",
                        "Encerrar sem qualquer registro.",
                    ],
                ),
                (
                    "Depois de uma correção, qual validação é mais completa?",
                    "Testar o fluxo real, confirmar os dispositivos e obter aceite do responsável.",
                    [
                        "Verificar apenas se uma luz acendeu.",
                        "Desligar o equipamento logo após a alteração.",
                        "Considerar concluído sem simular a operação.",
                    ],
                ),
                (
                    "Por que alterar somente uma variável por vez durante o diagnóstico?",
                    "Para relacionar o resultado à ação executada e preservar a rastreabilidade.",
                    [
                        "Para aumentar propositalmente o tempo do atendimento.",
                        "Para evitar o preenchimento da ordem de serviço.",
                        "Para eliminar a necessidade de testes finais.",
                    ],
                ),
            ],
        )
        return curso

    def _criar_questoes(self, etapa, questoes):
        for ordem, (enunciado, correta, incorretas) in enumerate(questoes, start=1):
            questao = Questao.objects.create(
                etapa=etapa, enunciado=enunciado, ordem=ordem
            )
            posicao_correta = (ordem * 2 - 1) % 4
            respostas = list(incorretas)
            respostas.insert(posicao_correta, correta)
            for indice, texto in enumerate(respostas):
                Alternativa.objects.create(
                    questao=questao,
                    texto=texto,
                    correta=indice == posicao_correta,
                    ordem=indice + 1,
                )

    def _texto_seguranca(self, dados):
        return f"""
Objetivo

Antes de qualquer manutenção, o técnico deve compreender o ambiente, confirmar
o chamado e combinar a intervenção com o responsável pelo local.

1. Confirme o sintoma

Peça ao operador que descreva quando a falha começou, sua frequência e o impacto
na operação. Não presuma que o primeiro relato já representa a causa.

2. Torne o ambiente seguro

Na {dados['contexto']}, considere especialmente: {dados['risco']}. A ação inicial
recomendada nesta simulação é {dados['acao_segura']}.

3. Preserve o cenário

Antes de reiniciar, desconectar ou substituir componentes, registre mensagens,
indicadores, conexões e condições que possam ajudar a explicar a ocorrência.

4. Comunique o plano

Explique ao responsável quais testes serão realizados, o impacto esperado e como
a operação será validada ao final.

Importante

Este material é fictício e serve para validar a plataforma. Procedimentos reais
devem ser revisados e aprovados pelas áreas técnicas e de segurança da empresa.
""".strip()

    def _texto_diagnostico(self, dados):
        return f"""
Diagnóstico em camadas

Use uma sequência previsível para evitar trocas desnecessárias:

• Camada física: verifique danos, fixação, sujeira, conectores e sinais visuais.
• Energia: confirme alimentação, proteção, aterramento e estabilidade.
• Comunicação: valide cabos, rede, indicadores e comunicação entre dispositivos.
• Aplicação: consulte mensagens, eventos e comportamento do fluxo operacional.

Para este curso, a inspeção inicial deve considerar {dados['verificacao']}.

Teste de hipótese

Formule uma hipótese por vez, execute uma alteração controlada e compare o
resultado. Alterações simultâneas dificultam a identificação da causa real.

Validação final

Depois da correção, simule o uso normal de {dados['equipamento']}, confirme os
dispositivos envolvidos e solicite ao responsável que valide a operação.

Registro obrigatório

Documente o sintoma, as evidências, a causa encontrada, a ação executada, peças
utilizadas e o resultado do teste final. Um bom registro ajuda no próximo
atendimento e permite identificar falhas recorrentes.
""".strip()
