import csv
from collections import defaultdict
from io import TextIOWrapper
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .audit import registrar_evento
from .emails import enviar_convite_responsavel
from .forms import (
    AlternativaForm,
    CursoForm,
    EmpresaForm,
    ImportarTecnicosForm,
    ImportarLiberacoesForm,
    EtapaCursoForm,
    LiberarCursoLoteForm,
    PrimeiroAcessoForm,
    ProdutoForm,
    QuestaoForm,
    ResponsavelEmpresaForm,
    TecnicoForm,
    ValidarCertificadoForm,
)
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

from .scopes import (
    empresas_do_usuario,
    papeis_responsavel_usuario,
    usuario_pode_gerenciar_catalogo,
    usuario_pode_operar_empresas,
)

JANELA_VENCIMENTO_DIAS = 30
EMPRESA_CONTEXTO_SESSION_KEY = "empresa_operacional_id"


def _redirect_conteudo_curso(curso_id, anchor=""):
    url = reverse("conteudo_curso_operacional", args=(curso_id,))
    if anchor:
        url = f"{url}#{anchor}"
    return HttpResponseRedirect(url)


def saude(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "erro", "database": "indisponivel"}, status=503)

    return JsonResponse({"status": "ok", "database": "ok"})


def _situacao_certificado(conclusao):
    if not conclusao.data_vencimento:
        return "Sem vencimento", "status-pendente"
    if conclusao.data_vencimento < timezone.localdate():
        return "Vencido", "status-vencido"
    return "Válido", "status-em-dia"


def _situacao_liberacao(liberacao, hoje=None):
    hoje = hoje or timezone.localdate()
    limite = hoje + timedelta(days=JANELA_VENCIMENTO_DIAS)
    tecnico = liberacao.tecnico
    curso = liberacao.curso
    ultima_conclusao = curso.conclusoes.filter(tecnico=tecnico).order_by(
        "-data_conclusao"
    ).first()
    progresso = curso.progressos.filter(tecnico=tecnico).first()

    if ultima_conclusao and ultima_conclusao.data_vencimento:
        if ultima_conclusao.data_vencimento < hoje:
            return ultima_conclusao, progresso, "vencido", "Vencido", "status-vencido"
        if ultima_conclusao.data_vencimento <= limite:
            return (
                ultima_conclusao,
                progresso,
                "vence_30",
                "Vence em até 30 dias",
                "status-pendente",
            )
        return ultima_conclusao, progresso, "em_dia", "Em dia", "status-em-dia"

    if ultima_conclusao:
        return (
            ultima_conclusao,
            progresso,
            "sem_vencimento",
            "Sem vencimento",
            "status-pendente",
        )

    if progresso and progresso.status == ProgressoCurso.Status.EM_ANDAMENTO:
        return (
            ultima_conclusao,
            progresso,
            "em_andamento",
            "Em andamento",
            "status-andamento",
        )

    return ultima_conclusao, progresso, "pendente", "Pendente", "status-pendente"


def _totais_relatorio_vazios():
    return {
        "total": 0,
        "pendente": 0,
        "em_andamento": 0,
        "em_dia": 0,
        "vence_30": 0,
        "vencido": 0,
        "sem_vencimento": 0,
    }


def _incrementar_totais(totais, situacao):
    totais["total"] += 1
    totais[situacao] += 1


def _risco_total(totais):
    return totais["pendente"] + totais["vence_30"] + totais["vencido"]


def _montar_relatorio_treinamentos(usuario, empresa_id="", situacao_filtro=""):
    hoje = timezone.localdate()
    empresas = empresas_do_usuario(usuario).order_by("nome")
    liberacoes = CursoLiberado.objects.filter(
        ativo=True,
        tecnico__ativo=True,
        curso__ativo=True,
        tecnico__empresa__in=empresas,
    ).select_related("tecnico__empresa", "curso__produto")

    if empresa_id:
        liberacoes = liberacoes.filter(tecnico__empresa_id=empresa_id)

    itens = []
    totais = _totais_relatorio_vazios()
    resumo_empresas = defaultdict(_totais_relatorio_vazios)
    resumo_cursos = defaultdict(_totais_relatorio_vazios)
    nomes_empresas = {}
    nomes_cursos = {}

    for liberacao in liberacoes.order_by(
        "tecnico__empresa__nome",
        "tecnico__nome",
        "curso__produto__nome",
        "curso__nome",
    ):
        ultima_conclusao, progresso, situacao, rotulo, classe = _situacao_liberacao(
            liberacao,
            hoje=hoje,
        )
        if situacao_filtro and situacao != situacao_filtro:
            continue

        empresa = liberacao.tecnico.empresa
        curso = liberacao.curso
        _incrementar_totais(totais, situacao)
        _incrementar_totais(resumo_empresas[empresa.id], situacao)
        _incrementar_totais(resumo_cursos[curso.id], situacao)
        nomes_empresas[empresa.id] = empresa.nome
        nomes_cursos[curso.id] = f"{curso.produto.nome} - {curso.nome}"
        itens.append(
            {
                "liberacao": liberacao,
                "ultima_conclusao": ultima_conclusao,
                "progresso": progresso,
                "situacao": situacao,
                "rotulo": rotulo,
                "classe": classe,
            }
        )

    empresas_resumo = [
        {
            "nome": nomes_empresas[empresa_id],
            "totais": totais_empresa,
            "risco": _risco_total(totais_empresa),
        }
        for empresa_id, totais_empresa in resumo_empresas.items()
    ]
    cursos_resumo = [
        {
            "nome": nomes_cursos[curso_id],
            "totais": totais_curso,
            "risco": _risco_total(totais_curso),
        }
        for curso_id, totais_curso in resumo_cursos.items()
    ]
    empresas_resumo.sort(key=lambda item: (-item["risco"], item["nome"]))
    cursos_resumo.sort(key=lambda item: (-item["risco"], item["nome"]))

    return {
        "empresas": empresas,
        "itens": itens,
        "totais": totais,
        "resumo_empresas": empresas_resumo,
        "resumo_cursos": cursos_resumo,
    }


def _buscar_conclusao_por_codigo(codigo):
    form = ValidarCertificadoForm({"codigo": codigo})
    if not form.is_valid():
        return None, ""

    codigo_normalizado = form.cleaned_data["codigo"]
    conclusao = (
        ConclusaoTreinamento.objects.select_related(
            "tecnico__empresa",
            "curso__produto",
        )
        .filter(codigo_certificado=codigo_normalizado)
        .first()
    )
    return conclusao, codigo_normalizado


def _tecnico_logado(request):
    try:
        return request.user.tecnico
    except Tecnico.DoesNotExist:
        return None


def _usuario_pode_testar_cursos(user, empresa):
    if not usuario_pode_gerenciar_catalogo(user):
        return False
    return empresas_do_usuario(user).filter(pk=empresa.pk).exists()


def _tecnico_teste_interno(user, empresa):
    nome = user.get_full_name() or user.username or f"Usuario {user.pk}"
    tecnico, _ = Tecnico.objects.get_or_create(
        matricula=f"TESTE-{user.pk}-{empresa.pk}",
        defaults={
            "empresa": empresa,
            "nome": f"Teste interno - {nome}",
            "email": f"teste-{user.pk}-{empresa.pk}@academia.local",
            "equipe": "Teste interno da plataforma",
            "regiao": "Ambiente de testes",
            "ativo": True,
        },
    )
    campos_atualizar = []
    if tecnico.empresa_id != empresa.pk:
        tecnico.empresa = empresa
        campos_atualizar.append("empresa")
    if not tecnico.ativo:
        tecnico.ativo = True
        campos_atualizar.append("ativo")
    if campos_atualizar:
        tecnico.save(update_fields=campos_atualizar)
    return tecnico


def _tecnico_para_produto(request, produto):
    tecnico = _tecnico_logado(request)
    if tecnico and tecnico.empresa_id == produto.empresa_id:
        return tecnico
    if _usuario_pode_testar_cursos(request.user, produto.empresa):
        tecnico = _tecnico_teste_interno(request.user, produto.empresa)
        for curso in produto.cursos.filter(ativo=True):
            CursoLiberado.objects.get_or_create(
                tecnico=tecnico,
                curso=curso,
                defaults={"obrigatorio": False, "ativo": True},
            )
        return tecnico
    return None


def _tecnico_para_curso(request, curso):
    tecnico = _tecnico_logado(request)
    if tecnico and tecnico.empresa_id == curso.produto.empresa_id:
        return tecnico
    if _usuario_pode_testar_cursos(request.user, curso.produto.empresa):
        tecnico = _tecnico_teste_interno(request.user, curso.produto.empresa)
        CursoLiberado.objects.get_or_create(
            tecnico=tecnico,
            curso=curso,
            defaults={"obrigatorio": False, "ativo": True},
        )
        return tecnico
    return None


def _curso_liberado(tecnico, curso):
    return CursoLiberado.objects.filter(
        tecnico=tecnico, curso=curso, curso__ativo=True, ativo=True
    ).exists()


def _responsaveis_visiveis(request):
    responsaveis = ResponsavelEmpresa.objects.filter(
        empresa__in=empresas_do_usuario(request.user)
    ).select_related("empresa", "usuario")
    empresa = _empresa_contexto(request)
    if empresa is not None:
        responsaveis = responsaveis.filter(empresa=empresa)
    return responsaveis


def _empresas_visiveis(request):
    if request.user.is_superuser:
        return empresas_do_usuario(request.user, incluir_inativas=True)
    return empresas_do_usuario(request.user)


def _empresa_contexto(request):
    empresas = _empresas_visiveis(request).filter(ativa=True)
    empresa_id = request.session.get(EMPRESA_CONTEXTO_SESSION_KEY)
    if empresa_id:
        empresa = empresas.filter(pk=empresa_id).first()
        if empresa:
            return empresa
        request.session.pop(EMPRESA_CONTEXTO_SESSION_KEY, None)

    if empresas.count() == 1:
        empresa = empresas.first()
        request.session[EMPRESA_CONTEXTO_SESSION_KEY] = empresa.id
        return empresa

    return None


def _empresa_contexto_obrigatoria(request):
    empresa = _empresa_contexto(request)
    if empresa is None:
        messages.warning(request, "Selecione uma empresa para continuar.")
    return empresa


def _definir_empresa_contexto(request, empresa):
    request.session[EMPRESA_CONTEXTO_SESSION_KEY] = empresa.id


def _tecnicos_visiveis(request):
    empresas = _empresas_visiveis(request)
    empresa = _empresa_contexto(request)
    if empresa is not None:
        empresas = empresas.filter(pk=empresa.pk)
    return Tecnico.objects.filter(empresa__in=empresas).select_related(
        "empresa",
        "usuario",
    )


def _produtos_contexto(request):
    empresa = _empresa_contexto(request)
    if empresa is None:
        return Produto.objects.none()
    return Produto.objects.filter(empresa=empresa)


def _cursos_contexto(request):
    empresa = _empresa_contexto(request)
    if empresa is None:
        return Curso.objects.none()
    return Curso.objects.filter(produto__empresa=empresa)


def _registrar_exclusao(request, alvo_tipo, alvo_id, alvo_repr, empresa=None):
    EventoAuditoria.objects.create(
        usuario=request.user,
        empresa=empresa,
        acao=EventoAuditoria.Acao.EDICAO,
        alvo_tipo=alvo_tipo,
        alvo_id=alvo_id,
        alvo_repr=str(alvo_repr)[:255],
        detalhes=f"{alvo_tipo} excluido pela tela operacional.",
    )


def _excluir_curso_com_dependencias(curso):
    ConclusaoTreinamento.objects.filter(curso=curso).delete()
    CursoLiberado.objects.filter(curso=curso).delete()
    ProgressoCurso.objects.filter(curso=curso).delete()
    curso.delete()


def _excluir_produto_com_dependencias(produto):
    for curso in produto.cursos.all():
        _excluir_curso_com_dependencias(curso)
    produto.delete()


def _excluir_tecnico_com_dependencias(tecnico):
    ConclusaoTreinamento.objects.filter(tecnico=tecnico).delete()
    CursoLiberado.objects.filter(tecnico=tecnico).delete()
    ProgressoCurso.objects.filter(tecnico=tecnico).delete()
    tecnico.delete()


def _excluir_empresa_com_dependencias(empresa):
    ResponsavelEmpresa.objects.filter(empresa=empresa).delete()
    for produto in empresa.produtos.all():
        _excluir_produto_com_dependencias(produto)
    for tecnico in empresa.tecnicos.all():
        _excluir_tecnico_com_dependencias(tecnico)
    EventoAuditoria.objects.filter(empresa=empresa).delete()
    empresa.delete()


def _valor_booleano_csv(valor):
    if valor is None or str(valor).strip() == "":
        return True
    return str(valor).strip().lower() in {"1", "sim", "s", "true", "ativo", "x"}


def _linhas_csv_tecnicos(arquivo):
    texto = TextIOWrapper(arquivo.file, encoding="utf-8-sig", newline="")
    amostra = texto.read(2048)
    texto.seek(0)
    try:
        dialecto = csv.Sniffer().sniff(amostra, delimiters=",;")
    except csv.Error:
        dialecto = csv.excel
    leitor = csv.DictReader(texto, dialect=dialecto)
    if not leitor.fieldnames:
        return [], ["O arquivo CSV esta vazio."]

    colunas = {coluna.strip().lower() for coluna in leitor.fieldnames if coluna}
    obrigatorias = {"nome", "email", "matricula"}
    faltantes = sorted(obrigatorias - colunas)
    if faltantes:
        return [], [f"Colunas obrigatorias ausentes: {', '.join(faltantes)}."]

    linhas = []
    for numero, linha in enumerate(leitor, start=2):
        normalizada = {
            (chave or "").strip().lower(): (valor or "").strip()
            for chave, valor in linha.items()
        }
        if not any(normalizada.values()):
            continue
        linhas.append((numero, normalizada))
    return linhas, []


def _importar_tecnicos_csv(empresa, arquivo):
    linhas, erros = _linhas_csv_tecnicos(arquivo)
    dados_validos = []
    matriculas_no_arquivo = set()
    emails_no_arquivo = set()

    for numero, linha in linhas:
        nome = linha.get("nome", "")
        email = linha.get("email", "").lower()
        matricula = linha.get("matricula", "")

        if not nome:
            erros.append(f"Linha {numero}: nome e obrigatorio.")
        if not email:
            erros.append(f"Linha {numero}: email e obrigatorio.")
        if not matricula:
            erros.append(f"Linha {numero}: matricula e obrigatoria.")

        if matricula and matricula in matriculas_no_arquivo:
            erros.append(f"Linha {numero}: matricula duplicada no arquivo.")
        if email and email in emails_no_arquivo:
            erros.append(f"Linha {numero}: email duplicado no arquivo.")
        matriculas_no_arquivo.add(matricula)
        emails_no_arquivo.add(email)

        tecnico_por_email = Tecnico.objects.filter(email__iexact=email).first()
        tecnico_por_matricula = Tecnico.objects.filter(matricula=matricula).first()
        existente = tecnico_por_matricula or tecnico_por_email
        if tecnico_por_email and tecnico_por_matricula and tecnico_por_email != tecnico_por_matricula:
            erros.append(
                f"Linha {numero}: email e matricula pertencem a tecnicos diferentes."
            )
        if existente and existente.empresa_id != empresa.id:
            erros.append(
                f"Linha {numero}: tecnico ja existe em outra empresa."
            )

        dados_validos.append(
            {
                "existente": existente,
                "nome": nome,
                "email": email,
                "matricula": matricula,
                "telefone": linha.get("telefone", ""),
                "equipe": linha.get("equipe", ""),
                "regiao": linha.get("regiao", ""),
                "ativo": _valor_booleano_csv(linha.get("ativo")),
            }
        )

    if erros:
        return {"criados": 0, "atualizados": 0, "erros": erros}

    resultado = {"criados": 0, "atualizados": 0, "erros": []}
    with transaction.atomic():
        for item in dados_validos:
            tecnico = item.pop("existente")
            if tecnico:
                for campo, valor in item.items():
                    setattr(tecnico, campo, valor)
                tecnico.empresa = empresa
                tecnico.save()
                resultado["atualizados"] += 1
            else:
                Tecnico.objects.create(empresa=empresa, **item)
                resultado["criados"] += 1
    return resultado


def _linhas_csv_liberacoes(arquivo):
    texto = TextIOWrapper(arquivo.file, encoding="utf-8-sig", newline="")
    amostra = texto.read(2048)
    texto.seek(0)
    try:
        dialecto = csv.Sniffer().sniff(amostra, delimiters=",;")
    except csv.Error:
        dialecto = csv.excel
    leitor = csv.DictReader(texto, dialect=dialecto)
    if not leitor.fieldnames:
        return [], ["O arquivo CSV esta vazio."]

    colunas = {coluna.strip().lower() for coluna in leitor.fieldnames if coluna}
    if not {"matricula", "email"} & colunas:
        return [], ["Informe ao menos uma coluna: matricula ou email."]

    linhas = []
    for numero, linha in enumerate(leitor, start=2):
        normalizada = {
            (chave or "").strip().lower(): (valor or "").strip()
            for chave, valor in linha.items()
        }
        if not any(normalizada.values()):
            continue
        linhas.append((numero, normalizada))
    return linhas, []


def _importar_liberacoes_csv(empresa, curso, arquivo, obrigatorio_padrao):
    linhas, erros = _linhas_csv_liberacoes(arquivo)
    dados_validos = []
    tecnicos_no_arquivo = set()

    for numero, linha in linhas:
        matricula = linha.get("matricula", "")
        email = linha.get("email", "").lower()
        if not matricula and not email:
            erros.append(f"Linha {numero}: informe matricula ou email.")
            continue

        tecnico_por_matricula = (
            Tecnico.objects.filter(matricula=matricula).first() if matricula else None
        )
        tecnico_por_email = (
            Tecnico.objects.filter(email__iexact=email).first() if email else None
        )
        tecnico = tecnico_por_matricula or tecnico_por_email

        if tecnico_por_matricula and tecnico_por_email and tecnico_por_matricula != tecnico_por_email:
            erros.append(
                f"Linha {numero}: email e matricula pertencem a tecnicos diferentes."
            )
            continue

        if not tecnico:
            erros.append(f"Linha {numero}: tecnico nao encontrado.")
            continue

        if tecnico.empresa_id != empresa.id:
            erros.append(f"Linha {numero}: tecnico pertence a outra empresa.")
            continue

        if not tecnico.ativo:
            erros.append(f"Linha {numero}: tecnico inativo.")
            continue

        if tecnico.id in tecnicos_no_arquivo:
            erros.append(f"Linha {numero}: tecnico duplicado no arquivo.")
            continue
        tecnicos_no_arquivo.add(tecnico.id)

        obrigatorio = (
            _valor_booleano_csv(linha.get("obrigatorio"))
            if linha.get("obrigatorio", "") != ""
            else obrigatorio_padrao
        )
        dados_validos.append({"tecnico": tecnico, "obrigatorio": obrigatorio})

    if erros:
        return {"criados": 0, "reativados": 0, "existentes": 0, "erros": erros}

    resultado = {"criados": 0, "reativados": 0, "existentes": 0, "erros": []}
    with transaction.atomic():
        for item in dados_validos:
            liberacao, criada = CursoLiberado.objects.get_or_create(
                tecnico=item["tecnico"],
                curso=curso,
                defaults={"obrigatorio": item["obrigatorio"], "ativo": True},
            )
            if criada:
                resultado["criados"] += 1
            elif not liberacao.ativo or liberacao.obrigatorio != item["obrigatorio"]:
                liberacao.ativo = True
                liberacao.obrigatorio = item["obrigatorio"]
                liberacao.save(update_fields=["ativo", "obrigatorio"])
                resultado["reativados"] += 1
            else:
                resultado["existentes"] += 1
    return resultado


def _exigir_editor_catalogo(request):
    if not usuario_pode_gerenciar_catalogo(request.user):
        raise PermissionDenied


def _exigir_operador_empresas(request):
    if not usuario_pode_operar_empresas(request.user):
        raise PermissionDenied


def _contexto_etapas(curso, progresso):
    etapas = list(curso.etapas.filter(ativo=True))
    concluidas = {
        item.etapa_id: item
        for item in progresso.etapas_concluidas.filter(
            tentativa=progresso.tentativa_atual
        )
    }
    primeira_pendente = next(
        (etapa for etapa in etapas if etapa.id not in concluidas), None
    )

    itens = []
    for etapa in etapas:
        concluida = etapa.id in concluidas
        liberada = concluida or etapa == primeira_pendente
        itens.append(
            {
                "etapa": etapa,
                "concluida": concluida,
                "liberada": liberada,
                "progresso": concluidas.get(etapa.id),
            }
        )
    return etapas, concluidas, primeira_pendente, itens


@login_required
def home(request):
    pode_operar = usuario_pode_operar_empresas(request.user)
    pode_catalogo = usuario_pode_gerenciar_catalogo(request.user)

    if request.user.is_superuser:
        empresas = empresas_do_usuario(request.user, incluir_inativas=True).order_by(
            "nome"
        )
        resumo_superadmin = {
            "empresas": empresas.count(),
            "tecnicos": Tecnico.objects.count(),
            "liberacoes": CursoLiberado.objects.filter(ativo=True).count(),
            "produtos": Produto.objects.filter(ativo=True).count(),
            "cursos": Curso.objects.filter(ativo=True).count(),
        }
        return render(
            request,
            "core/home.html",
            {
                "painel_superadmin": True,
                "empresas": empresas,
                "resumo_operacional": resumo_superadmin,
            },
        )

    if request.user.is_staff and (pode_operar or pode_catalogo):
        return _render_painel_empresa(request, _empresa_contexto(request))

    produtos = Produto.objects.filter(
        ativo=True,
        cursos__ativo=True,
        cursos__liberacoes__tecnico__usuario=request.user,
        cursos__liberacoes__ativo=True,
    ).distinct().order_by("nome")
    return render(request, "core/home.html", {"produtos": produtos})


def _contexto_painel_empresa(request, empresa_contexto):
    pode_operar = usuario_pode_operar_empresas(request.user)
    pode_catalogo = usuario_pode_gerenciar_catalogo(request.user)
    empresas = empresas_do_usuario(request.user)
    empresas_resumo = (
        empresas.filter(pk=empresa_contexto.pk) if empresa_contexto else empresas
    )
    papeis = papeis_responsavel_usuario(request.user)
    resumo_operacional = {
        "empresas": empresas_resumo.count(),
        "tecnicos": Tecnico.objects.filter(empresa__in=empresas_resumo).count(),
        "liberacoes": CursoLiberado.objects.filter(
            tecnico__empresa__in=empresas_resumo,
            ativo=True,
        ).count(),
        "produtos": Produto.objects.filter(
            ativo=True,
            empresa__in=empresas_resumo,
        ).count()
        if pode_catalogo
        else None,
        "cursos": Curso.objects.filter(
            ativo=True,
            produto__empresa__in=empresas_resumo,
        ).count()
        if pode_catalogo
        else None,
    }
    atalhos = []
    if pode_operar:
        atalhos.extend(
            [
                {
                    "titulo": "Liberar cursos",
                    "texto": "Crie liberações para técnicos das suas empresas.",
                    "url": "liberar_curso_lote",
                },
                {
                    "titulo": "Relatórios",
                    "texto": "Acompanhe pendências, vencimentos e certificados.",
                    "url": "relatorio_treinamentos",
                },
                {
                    "titulo": "Técnicos",
                    "texto": "Cadastre e atualize profissionais por empresa.",
                    "url": "tecnicos_operacionais",
                },
            ]
        )
    if pode_catalogo:
        atalhos.append(
            {
                "titulo": "Cursos",
                "texto": "Gerencie cursos e construa etapas, questoes e alternativas.",
                "url": "cursos_operacionais",
            }
        )

    return {
        "painel_operacional": True,
        "pode_operar": pode_operar,
        "pode_catalogo": pode_catalogo,
        "empresas": empresas,
        "empresa_contexto_painel": empresa_contexto,
        "papeis": papeis,
        "resumo_operacional": resumo_operacional,
        "atalhos": atalhos,
    }


def _render_painel_empresa(request, empresa_contexto):
    return render(
        request,
        "core/home.html",
        _contexto_painel_empresa(request, empresa_contexto),
    )


def primeiro_acesso(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = PrimeiroAcessoForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].lower()
            matricula = form.cleaned_data["matricula"]
            senha = form.cleaned_data["senha"]

            try:
                tecnico = Tecnico.objects.get(
                    email__iexact=email, matricula=matricula, ativo=True
                )
            except Tecnico.DoesNotExist:
                messages.error(
                    request,
                    "Não encontramos um técnico ativo com esse e-mail e matrícula.",
                )
                return render(request, "core/primeiro_acesso.html", {"form": form})

            if tecnico.usuario:
                messages.warning(
                    request,
                    "Este técnico já possui usuário cadastrado. Faça login normalmente.",
                )
                return redirect("login")

            usuario = User.objects.create_user(
                username=email,
                email=email,
                password=senha,
                first_name=tecnico.nome.split()[0],
            )
            tecnico.usuario = usuario
            tecnico.save(update_fields=["usuario"])
            messages.success(request, "Usuário criado. Agora faça seu login.")
            return redirect("login")
    else:
        form = PrimeiroAcessoForm()

    return render(request, "core/primeiro_acesso.html", {"form": form})


def validar_certificado(request, codigo=None):
    codigo_inicial = codigo or request.GET.get("codigo", "")
    form = ValidarCertificadoForm(
        request.GET or None,
        initial={"codigo": codigo_inicial},
    )
    conclusao = None
    codigo_consultado = ""

    if codigo:
        form = ValidarCertificadoForm({"codigo": codigo})

    if form.is_bound and form.is_valid():
        codigo_consultado = form.cleaned_data["codigo"]
        conclusao, _ = _buscar_conclusao_por_codigo(codigo_consultado)

    contexto = {
        "form": form,
        "conclusao": conclusao,
        "codigo_consultado": codigo_consultado,
    }
    if conclusao:
        situacao, status_classe = _situacao_certificado(conclusao)
        contexto.update({"situacao": situacao, "status_classe": status_classe})

    return render(request, "core/validar_certificado.html", contexto)


@staff_member_required
def relatorio_treinamentos(request):
    _exigir_operador_empresas(request)
    empresa_contexto = _empresa_contexto(request)
    empresa_id = (
        str(empresa_contexto.id)
        if empresa_contexto
        else request.GET.get("empresa") or ""
    )
    situacao_filtro = request.GET.get("situacao") or ""
    relatorio = _montar_relatorio_treinamentos(
        request.user,
        empresa_id=empresa_id,
        situacao_filtro=situacao_filtro,
    )

    return render(
        request,
        "core/relatorio_treinamentos.html",
        {
            "empresas": relatorio["empresas"],
            "empresa_id": empresa_id,
            "situacao_filtro": situacao_filtro,
            "itens": relatorio["itens"],
            "totais": relatorio["totais"],
            "resumo_empresas": relatorio["resumo_empresas"],
            "resumo_cursos": relatorio["resumo_cursos"],
        },
    )


@staff_member_required
def exportar_relatorio_treinamentos(request):
    _exigir_operador_empresas(request)
    empresa_contexto = _empresa_contexto(request)
    relatorio = _montar_relatorio_treinamentos(
        request.user,
        empresa_id=str(empresa_contexto.id)
        if empresa_contexto
        else request.GET.get("empresa") or "",
        situacao_filtro=request.GET.get("situacao") or "",
    )
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = (
        'attachment; filename="relatorio_treinamentos.csv"'
    )
    resposta.write("\ufeff")
    escritor = csv.writer(resposta, delimiter=";")
    escritor.writerow(
        [
            "Empresa",
            "Tecnico",
            "Matricula",
            "Produto",
            "Curso",
            "Situacao",
            "Conclusao",
            "Validade",
            "Certificado",
        ]
    )

    for item in relatorio["itens"]:
        liberacao = item["liberacao"]
        conclusao = item["ultima_conclusao"]
        escritor.writerow(
            [
                liberacao.tecnico.empresa.nome,
                liberacao.tecnico.nome,
                liberacao.tecnico.matricula,
                liberacao.curso.produto.nome,
                liberacao.curso.nome,
                item["rotulo"],
                conclusao.data_conclusao.strftime("%d/%m/%Y") if conclusao else "",
                conclusao.data_vencimento.strftime("%d/%m/%Y")
                if conclusao and conclusao.data_vencimento
                else "",
                conclusao.codigo_certificado if conclusao else "",
            ]
        )
    return resposta


@staff_member_required
def historico_operacional(request):
    _exigir_operador_empresas(request)
    empresa_contexto = _empresa_contexto(request)
    empresas = empresas_do_usuario(request.user)
    if empresa_contexto:
        empresas = empresas.filter(pk=empresa_contexto.pk)
    empresas = empresas.order_by("nome")
    empresa_id = (
        str(empresa_contexto.id)
        if empresa_contexto
        else request.GET.get("empresa") or ""
    )
    acao = request.GET.get("acao") or ""
    busca = request.GET.get("q", "").strip()

    eventos = EventoAuditoria.objects.filter(empresa__in=empresas).select_related(
        "usuario",
        "empresa",
    )
    if empresa_id:
        eventos = eventos.filter(empresa_id=empresa_id)
    if acao:
        eventos = eventos.filter(acao=acao)
    if busca:
        eventos = eventos.filter(
            Q(alvo_repr__icontains=busca)
            | Q(detalhes__icontains=busca)
            | Q(usuario__username__icontains=busca)
            | Q(usuario__email__icontains=busca)
        )

    eventos = eventos.order_by("-criado_em", "-id")[:200]
    return render(
        request,
        "core/historico_operacional.html",
        {
            "eventos": eventos,
            "empresas": empresas,
            "empresa_id": empresa_id,
            "acao": acao,
            "busca": busca,
            "acoes": EventoAuditoria.Acao.choices,
        },
    )


@staff_member_required
@transaction.atomic
def liberar_curso_lote(request):
    _exigir_operador_empresas(request)
    empresa_contexto = _empresa_contexto(request)
    resultado = None
    importacao_form = ImportarLiberacoesForm(
        usuario=request.user,
        empresa_contexto=empresa_contexto,
        initial={"empresa": empresa_contexto} if empresa_contexto else None,
    )
    resultado_importacao = None
    if request.method == "POST":
        form = LiberarCursoLoteForm(
            request.POST,
            usuario=request.user,
            empresa_contexto=empresa_contexto,
        )
        if form.is_valid():
            curso = form.cleaned_data["curso"]
            tecnicos = form.cleaned_data["tecnicos"]
            obrigatorio = form.cleaned_data["obrigatorio"]
            resultado = {"criados": 0, "reativados": 0, "existentes": 0}

            for tecnico in tecnicos:
                liberacao, criada = CursoLiberado.objects.get_or_create(
                    tecnico=tecnico,
                    curso=curso,
                    defaults={"obrigatorio": obrigatorio, "ativo": True},
                )
                if criada:
                    resultado["criados"] += 1
                    continue

                if not liberacao.ativo or liberacao.obrigatorio != obrigatorio:
                    liberacao.ativo = True
                    liberacao.obrigatorio = obrigatorio
                    liberacao.save(update_fields=["ativo", "obrigatorio"])
                    resultado["reativados"] += 1
                else:
                    resultado["existentes"] += 1

            messages.success(
                request,
                (
                    "Liberação em lote concluída: "
                    f"{resultado['criados']} criada(s), "
                    f"{resultado['reativados']} reativada(s)/atualizada(s), "
                    f"{resultado['existentes']} já existente(s)."
                ),
            )
            empresa = form.cleaned_data["empresa"]
            form = LiberarCursoLoteForm(
                initial={"empresa": empresa},
                usuario=request.user,
                empresa_contexto=empresa_contexto,
            )
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.LIBERACAO,
                curso,
                empresa=empresa,
                detalhes=(
                    f"Liberacao manual: {resultado['criados']} criada(s), "
                    f"{resultado['reativados']} reativada(s)/atualizada(s), "
                    f"{resultado['existentes']} existente(s)."
                ),
            )
    else:
        form = LiberarCursoLoteForm(
            usuario=request.user,
            empresa_contexto=empresa_contexto,
            initial={"empresa": empresa_contexto} if empresa_contexto else None,
        )

    return render(
        request,
        "core/liberar_curso_lote.html",
        {
            "form": form,
            "importacao_form": importacao_form,
            "resultado": resultado,
            "resultado_importacao": resultado_importacao,
        },
    )


@staff_member_required
def importar_liberacoes_operacionais(request):
    _exigir_operador_empresas(request)
    if request.method != "POST":
        return redirect("liberar_curso_lote")

    empresa_contexto = _empresa_contexto(request)
    form = ImportarLiberacoesForm(
        request.POST,
        request.FILES,
        usuario=request.user,
        empresa_contexto=empresa_contexto,
    )
    resultado_importacao = None
    if form.is_valid():
        resultado_importacao = _importar_liberacoes_csv(
            form.cleaned_data["empresa"],
            form.cleaned_data["curso"],
            form.cleaned_data["arquivo"],
            form.cleaned_data["obrigatorio"],
        )
        if resultado_importacao["erros"]:
            messages.error(
                request,
                "Importacao nao realizada. Corrija os erros do arquivo e tente novamente.",
            )
        else:
            messages.success(
                request,
                (
                    "Importacao concluida: "
                    f"{resultado_importacao['criados']} criada(s), "
                    f"{resultado_importacao['reativados']} reativada(s)/atualizada(s), "
                    f"{resultado_importacao['existentes']} ja existente(s)."
                ),
            )
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.IMPORTACAO,
                form.cleaned_data["curso"],
                empresa=form.cleaned_data["empresa"],
                detalhes=(
                    "Importacao CSV de liberacoes: "
                    f"{resultado_importacao['criados']} criada(s), "
                    f"{resultado_importacao['reativados']} reativada(s)/atualizada(s), "
                    f"{resultado_importacao['existentes']} existente(s)."
                ),
            )
            return redirect("liberar_curso_lote")

    return render(
        request,
        "core/liberar_curso_lote.html",
        {
            "form": LiberarCursoLoteForm(
                usuario=request.user,
                empresa_contexto=empresa_contexto,
                initial={"empresa": empresa_contexto} if empresa_contexto else None,
            ),
            "importacao_form": form,
            "resultado": None,
            "resultado_importacao": resultado_importacao,
        },
    )


@staff_member_required
def responsaveis_empresas(request):
    _exigir_operador_empresas(request)
    empresa_contexto = _empresa_contexto(request)
    if request.method == "POST":
        form = ResponsavelEmpresaForm(
            request.POST,
            usuario=request.user,
            empresa_contexto=empresa_contexto,
        )
        if form.is_valid():
            responsabilidade = form.save()
            enviar_convite_responsavel(
                request,
                responsabilidade.usuario,
                responsabilidade,
            )
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.CADASTRO,
                responsabilidade,
                empresa=responsabilidade.empresa,
                detalhes=(
                    "Responsavel salvo e convite enviado para "
                    f"{responsabilidade.usuario.email}."
                ),
            )
            messages.success(
                request,
                (
                    f"Responsavel {responsabilidade.usuario.email} salvo com "
                    "sucesso. O convite de acesso foi enviado por e-mail."
                ),
            )
            return redirect("responsaveis_empresas")
    else:
        form = ResponsavelEmpresaForm(
            usuario=request.user,
            empresa_contexto=empresa_contexto,
            initial={"empresa": empresa_contexto} if empresa_contexto else None,
        )

    responsaveis = _responsaveis_visiveis(request).order_by(
        "empresa__nome",
        "usuario__first_name",
        "usuario__email",
    )
    return render(
        request,
        "core/responsaveis_empresas.html",
        {"form": form, "responsaveis": responsaveis},
    )


@staff_member_required
def editar_responsavel_empresa(request, responsavel_id):
    _exigir_operador_empresas(request)
    responsabilidade = get_object_or_404(
        _responsaveis_visiveis(request),
        pk=responsavel_id,
    )
    if request.method == "POST":
        form = ResponsavelEmpresaForm(
            request.POST,
            usuario=request.user,
            instance=responsabilidade,
            empresa_contexto=_empresa_contexto(request),
        )
        if form.is_valid():
            form.save()
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.EDICAO,
                responsabilidade,
                empresa=responsabilidade.empresa,
                detalhes=f"Responsavel atualizado: {responsabilidade.usuario.email}.",
            )
            messages.success(request, "Responsável atualizado com sucesso.")
            return redirect("responsaveis_empresas")
    else:
        empresa_contexto = _empresa_contexto(request)
        form = ResponsavelEmpresaForm(
            usuario=request.user,
            instance=responsabilidade,
            empresa_contexto=empresa_contexto,
        )

    return render(
        request,
        "core/responsavel_empresa_form.html",
        {"form": form, "responsabilidade": responsabilidade},
    )


@staff_member_required
@require_POST
def alternar_responsavel_empresa(request, responsavel_id):
    _exigir_operador_empresas(request)
    responsabilidade = get_object_or_404(
        _responsaveis_visiveis(request),
        pk=responsavel_id,
    )
    responsabilidade.ativo = not responsabilidade.ativo
    responsabilidade.save()
    registrar_evento(
        request.user,
        EventoAuditoria.Acao.STATUS,
        responsabilidade,
        empresa=responsabilidade.empresa,
        detalhes=f"Status alterado para {'ativo' if responsabilidade.ativo else 'inativo'}.",
    )
    status = "ativado" if responsabilidade.ativo else "desativado"
    messages.success(request, f"Responsável {status} com sucesso.")
    return redirect("responsaveis_empresas")


@staff_member_required
@require_POST
def excluir_responsavel_empresa(request, responsavel_id):
    _exigir_operador_empresas(request)
    responsabilidade = get_object_or_404(
        _responsaveis_visiveis(request),
        pk=responsavel_id,
    )
    empresa = responsabilidade.empresa
    nome = responsabilidade.usuario.get_full_name() or responsabilidade.usuario.email
    alvo_id = responsabilidade.id
    responsabilidade.delete()
    _registrar_exclusao(request, "ResponsavelEmpresa", alvo_id, nome, empresa=empresa)
    messages.success(request, f"Responsavel {nome} excluido com sucesso.")
    return redirect("responsaveis_empresas")


@staff_member_required
@require_POST
def reenviar_convite_responsavel(request, responsavel_id):
    _exigir_operador_empresas(request)
    responsabilidade = get_object_or_404(
        _responsaveis_visiveis(request),
        pk=responsavel_id,
    )
    enviar_convite_responsavel(request, responsabilidade.usuario, responsabilidade)
    registrar_evento(
        request.user,
        EventoAuditoria.Acao.CONVITE,
        responsabilidade,
        empresa=responsabilidade.empresa,
        detalhes=f"Convite reenviado para {responsabilidade.usuario.email}.",
    )
    messages.success(
        request,
        f"Convite reenviado para {responsabilidade.usuario.email}.",
    )
    return redirect("responsaveis_empresas")


@staff_member_required
def empresas_operacionais(request):
    _exigir_operador_empresas(request)
    pode_criar = request.user.is_superuser
    if request.method == "POST":
        if not pode_criar:
            raise PermissionDenied
        form = EmpresaForm(request.POST)
        if form.is_valid():
            empresa = form.save()
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.CADASTRO,
                empresa,
                empresa=empresa,
                detalhes="Empresa criada pela tela operacional.",
            )
            messages.success(request, f"Empresa {empresa.nome} criada com sucesso.")
            return redirect("empresas_operacionais")
    else:
        form = EmpresaForm()

    empresas = _empresas_visiveis(request).order_by("nome")
    return render(
        request,
        "core/empresas_operacionais.html",
        {"empresas": empresas, "form": form, "pode_criar": pode_criar},
    )


@staff_member_required
@require_POST
def acessar_empresa_operacional(request, empresa_id):
    _exigir_operador_empresas(request)
    empresa = get_object_or_404(
        _empresas_visiveis(request).filter(ativa=True),
        pk=empresa_id,
    )
    _definir_empresa_contexto(request, empresa)
    messages.success(request, f"Você está operando a empresa {empresa.nome}.")
    return redirect("painel_empresa_operacional", empresa_id=empresa.id)


@staff_member_required
def painel_empresa_operacional(request, empresa_id):
    _exigir_operador_empresas(request)
    empresa = get_object_or_404(
        _empresas_visiveis(request).filter(ativa=True),
        pk=empresa_id,
    )
    _definir_empresa_contexto(request, empresa)
    return _render_painel_empresa(request, empresa)


@staff_member_required
def editar_empresa_operacional(request, empresa_id):
    _exigir_operador_empresas(request)
    empresa = get_object_or_404(_empresas_visiveis(request), pk=empresa_id)
    if request.method == "POST":
        form = EmpresaForm(request.POST, instance=empresa)
        if form.is_valid():
            empresa = form.save()
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.EDICAO,
                empresa,
                empresa=empresa,
                detalhes="Empresa atualizada pela tela operacional.",
            )
            messages.success(request, f"Empresa {empresa.nome} atualizada com sucesso.")
            return redirect("empresas_operacionais")
    else:
        form = EmpresaForm(instance=empresa)

    return render(
        request,
        "core/empresa_operacional_form.html",
        {"form": form, "empresa": empresa},
    )


@staff_member_required
@require_POST
def alternar_empresa_operacional(request, empresa_id):
    _exigir_operador_empresas(request)
    if not request.user.is_superuser:
        raise PermissionDenied
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    empresa.ativa = not empresa.ativa
    empresa.save(update_fields=["ativa"])
    registrar_evento(
        request.user,
        EventoAuditoria.Acao.STATUS,
        empresa,
        empresa=empresa,
        detalhes=f"Status alterado para {'ativa' if empresa.ativa else 'inativa'}.",
    )
    status = "ativada" if empresa.ativa else "desativada"
    messages.success(request, f"Empresa {status} com sucesso.")
    return redirect("empresas_operacionais")


@staff_member_required
@require_POST
def excluir_empresa_operacional(request, empresa_id):
    _exigir_operador_empresas(request)
    if not request.user.is_superuser:
        raise PermissionDenied
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    nome = empresa.nome
    with transaction.atomic():
        _excluir_empresa_com_dependencias(empresa)
        _registrar_exclusao(request, "Empresa", empresa_id, nome)
    if request.session.get(EMPRESA_CONTEXTO_SESSION_KEY) == empresa_id:
        request.session.pop(EMPRESA_CONTEXTO_SESSION_KEY, None)
    messages.success(request, f"Empresa {nome} excluida com todos os dados vinculados.")
    return redirect("empresas_operacionais")


@staff_member_required
def tecnicos_operacionais(request):
    _exigir_operador_empresas(request)
    empresa_contexto = _empresa_contexto(request)
    importacao_form = ImportarTecnicosForm(
        usuario=request.user,
        empresa_contexto=empresa_contexto,
        initial={"empresa": empresa_contexto} if empresa_contexto else None,
    )
    resultado_importacao = None
    if request.method == "POST":
        form = TecnicoForm(
            request.POST,
            usuario=request.user,
            empresa_contexto=empresa_contexto,
        )
        if form.is_valid():
            tecnico = form.save()
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.CADASTRO,
                tecnico,
                empresa=tecnico.empresa,
                detalhes="Tecnico salvo pela tela operacional.",
            )
            messages.success(request, f"Tecnico {tecnico.nome} salvo com sucesso.")
            return redirect("tecnicos_operacionais")
    else:
        form = TecnicoForm(
            usuario=request.user,
            empresa_contexto=empresa_contexto,
            initial={"empresa": empresa_contexto} if empresa_contexto else None,
        )

    tecnicos = _tecnicos_visiveis(request).order_by("empresa__nome", "nome")
    return render(
        request,
        "core/tecnicos_operacionais.html",
        {
            "form": form,
            "importacao_form": importacao_form,
            "resultado_importacao": resultado_importacao,
            "tecnicos": tecnicos,
        },
    )


@staff_member_required
@transaction.atomic
def importar_tecnicos_operacionais(request):
    _exigir_operador_empresas(request)
    if request.method != "POST":
        return redirect("tecnicos_operacionais")

    empresa_contexto = _empresa_contexto(request)
    form = ImportarTecnicosForm(
        request.POST,
        request.FILES,
        usuario=request.user,
        empresa_contexto=empresa_contexto,
    )
    resultado_importacao = None
    if form.is_valid():
        resultado_importacao = _importar_tecnicos_csv(
            form.cleaned_data["empresa"],
            form.cleaned_data["arquivo"],
        )
        if resultado_importacao["erros"]:
            messages.error(
                request,
                "Importacao nao realizada. Corrija os erros do arquivo e tente novamente.",
            )
        else:
            messages.success(
                request,
                (
                    "Importacao concluida: "
                    f"{resultado_importacao['criados']} criado(s), "
                    f"{resultado_importacao['atualizados']} atualizado(s)."
                ),
            )
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.IMPORTACAO,
                form.cleaned_data["empresa"],
                empresa=form.cleaned_data["empresa"],
                detalhes=(
                    "Importacao CSV de tecnicos: "
                    f"{resultado_importacao['criados']} criado(s), "
                    f"{resultado_importacao['atualizados']} atualizado(s)."
                ),
            )
            return redirect("tecnicos_operacionais")

    tecnicos = _tecnicos_visiveis(request).order_by("empresa__nome", "nome")
    cadastro_form = TecnicoForm(
        usuario=request.user,
        empresa_contexto=empresa_contexto,
        initial={"empresa": empresa_contexto} if empresa_contexto else None,
    )
    return render(
        request,
        "core/tecnicos_operacionais.html",
        {
            "form": cadastro_form,
            "importacao_form": form,
            "resultado_importacao": resultado_importacao,
            "tecnicos": tecnicos,
        },
    )


@staff_member_required
def editar_tecnico_operacional(request, tecnico_id):
    _exigir_operador_empresas(request)
    tecnico = get_object_or_404(_tecnicos_visiveis(request), pk=tecnico_id)
    if request.method == "POST":
        form = TecnicoForm(
            request.POST,
            usuario=request.user,
            empresa_contexto=_empresa_contexto(request),
            instance=tecnico,
        )
        if form.is_valid():
            tecnico = form.save()
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.EDICAO,
                tecnico,
                empresa=tecnico.empresa,
                detalhes="Tecnico atualizado pela tela operacional.",
            )
            messages.success(request, f"Tecnico {tecnico.nome} atualizado com sucesso.")
            return redirect("tecnicos_operacionais")
    else:
        form = TecnicoForm(
            usuario=request.user,
            empresa_contexto=_empresa_contexto(request),
            instance=tecnico,
        )

    return render(
        request,
        "core/tecnico_operacional_form.html",
        {"form": form, "tecnico": tecnico},
    )


@staff_member_required
@require_POST
def alternar_tecnico_operacional(request, tecnico_id):
    _exigir_operador_empresas(request)
    tecnico = get_object_or_404(_tecnicos_visiveis(request), pk=tecnico_id)
    tecnico.ativo = not tecnico.ativo
    tecnico.save(update_fields=["ativo"])
    registrar_evento(
        request.user,
        EventoAuditoria.Acao.STATUS,
        tecnico,
        empresa=tecnico.empresa,
        detalhes=f"Status alterado para {'ativo' if tecnico.ativo else 'inativo'}.",
    )
    status = "ativado" if tecnico.ativo else "desativado"
    messages.success(request, f"Tecnico {status} com sucesso.")
    return redirect("tecnicos_operacionais")


@staff_member_required
@require_POST
def excluir_tecnico_operacional(request, tecnico_id):
    _exigir_operador_empresas(request)
    tecnico = get_object_or_404(_tecnicos_visiveis(request), pk=tecnico_id)
    empresa = tecnico.empresa
    nome = tecnico.nome
    alvo_id = tecnico.id
    with transaction.atomic():
        _excluir_tecnico_com_dependencias(tecnico)
        _registrar_exclusao(request, "Tecnico", alvo_id, nome, empresa=empresa)
    messages.success(request, f"Tecnico {nome} excluido com sucesso.")
    return redirect("tecnicos_operacionais")


@staff_member_required
def produtos_operacionais(request):
    _exigir_editor_catalogo(request)
    empresa = _empresa_contexto_obrigatoria(request)
    if empresa is None:
        return redirect("empresas_operacionais")

    if request.method == "POST":
        form = ProdutoForm(request.POST)
        if form.is_valid():
            produto = form.save(commit=False)
            produto.empresa = empresa
            produto.save()
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.CADASTRO,
                produto,
                empresa=empresa,
                detalhes="Produto criado pela tela de catalogo.",
            )
            messages.success(request, f"Produto {produto.nome} salvo com sucesso.")
            return redirect("produtos_operacionais")
    else:
        form = ProdutoForm()

    produtos = _produtos_contexto(request).order_by("nome")
    return render(
        request,
        "core/produtos_operacionais.html",
        {"form": form, "produtos": produtos},
    )


@staff_member_required
def editar_produto_operacional(request, produto_id):
    _exigir_editor_catalogo(request)
    produto = get_object_or_404(
        Produto.objects.select_related("empresa").filter(
            empresa__in=_empresas_visiveis(request).filter(ativa=True)
        ),
        pk=produto_id,
    )
    empresa = _empresa_contexto(request)
    if empresa is None or empresa.pk != produto.empresa_id:
        empresa = produto.empresa
        _definir_empresa_contexto(request, empresa)
    if request.method == "POST":
        form = ProdutoForm(request.POST, instance=produto)
        if form.is_valid():
            produto = form.save()
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.EDICAO,
                produto,
                empresa=empresa,
                detalhes="Produto atualizado pela tela de catalogo.",
            )
            messages.success(request, f"Produto {produto.nome} atualizado com sucesso.")
            return redirect("produtos_operacionais")
    else:
        form = ProdutoForm(instance=produto)

    return render(
        request,
        "core/produto_operacional_form.html",
        {"form": form, "produto": produto},
    )


@staff_member_required
@require_POST
def alternar_produto_operacional(request, produto_id):
    _exigir_editor_catalogo(request)
    empresa = _empresa_contexto_obrigatoria(request)
    if empresa is None:
        return redirect("empresas_operacionais")

    produto = get_object_or_404(_produtos_contexto(request), pk=produto_id)
    produto.ativo = not produto.ativo
    produto.save(update_fields=["ativo"])
    registrar_evento(
        request.user,
        EventoAuditoria.Acao.STATUS,
        produto,
        empresa=empresa,
        detalhes=f"Status alterado para {'ativo' if produto.ativo else 'inativo'}.",
    )
    status = "ativado" if produto.ativo else "desativado"
    messages.success(request, f"Produto {status} com sucesso.")
    return redirect("produtos_operacionais")


@staff_member_required
@require_POST
def excluir_produto_operacional(request, produto_id):
    _exigir_editor_catalogo(request)
    empresa = _empresa_contexto_obrigatoria(request)
    if empresa is None:
        return redirect("empresas_operacionais")

    produto = get_object_or_404(_produtos_contexto(request), pk=produto_id)
    nome = produto.nome
    alvo_id = produto.id
    with transaction.atomic():
        _excluir_produto_com_dependencias(produto)
        _registrar_exclusao(request, "Produto", alvo_id, nome, empresa=empresa)
    messages.success(request, f"Produto {nome} excluido com sucesso.")
    return redirect("produtos_operacionais")


@staff_member_required
def cursos_operacionais(request):
    _exigir_editor_catalogo(request)
    empresa = _empresa_contexto_obrigatoria(request)
    if empresa is None:
        return redirect("empresas_operacionais")

    if request.method == "POST":
        form = CursoForm(request.POST, request.FILES, empresa=empresa)
        if form.is_valid():
            curso = form.save()
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.CADASTRO,
                curso,
                empresa=empresa,
                detalhes="Curso criado pela tela de catalogo.",
            )
            messages.success(request, f"Curso {curso.nome} salvo com sucesso.")
            return redirect("cursos_operacionais")
    else:
        form = CursoForm(empresa=empresa)

    cursos = (
        _cursos_contexto(request)
        .select_related("produto")
        .order_by("produto__nome", "nome")
    )
    return render(
        request,
        "core/cursos_operacionais.html",
        {"form": form, "cursos": cursos},
    )


@staff_member_required
def editar_curso_operacional(request, curso_id):
    _exigir_editor_catalogo(request)
    curso = get_object_or_404(
        Curso.objects.select_related("produto", "produto__empresa").filter(
            produto__empresa__in=_empresas_visiveis(request).filter(ativa=True)
        ),
        pk=curso_id,
    )
    empresa = _empresa_contexto(request)
    if empresa is None or empresa.pk != curso.produto.empresa_id:
        empresa = curso.produto.empresa
        _definir_empresa_contexto(request, empresa)
    if request.method == "POST":
        form = CursoForm(request.POST, request.FILES, instance=curso, empresa=empresa)
        if form.is_valid():
            curso = form.save()
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.EDICAO,
                curso,
                empresa=empresa,
                detalhes="Curso atualizado pela tela de catalogo.",
            )
            messages.success(request, f"Curso {curso.nome} atualizado com sucesso.")
            return redirect("cursos_operacionais")
    else:
        form = CursoForm(instance=curso, empresa=empresa)

    return render(
        request,
        "core/curso_operacional_form.html",
        {"form": form, "curso": curso},
    )


@staff_member_required
@require_POST
def alternar_curso_operacional(request, curso_id):
    _exigir_editor_catalogo(request)
    empresa = _empresa_contexto_obrigatoria(request)
    if empresa is None:
        return redirect("empresas_operacionais")

    curso = get_object_or_404(_cursos_contexto(request), pk=curso_id)
    curso.ativo = not curso.ativo
    curso.save(update_fields=["ativo"])
    registrar_evento(
        request.user,
        EventoAuditoria.Acao.STATUS,
        curso,
        empresa=empresa,
        detalhes=f"Status alterado para {'ativo' if curso.ativo else 'inativo'}.",
    )
    status = "ativado" if curso.ativo else "desativado"
    messages.success(request, f"Curso {status} com sucesso.")
    return redirect("cursos_operacionais")


@staff_member_required
@require_POST
def excluir_curso_operacional(request, curso_id):
    _exigir_editor_catalogo(request)
    empresa = _empresa_contexto_obrigatoria(request)
    if empresa is None:
        return redirect("empresas_operacionais")

    curso = get_object_or_404(_cursos_contexto(request), pk=curso_id)
    nome = curso.nome
    alvo_id = curso.id
    with transaction.atomic():
        _excluir_curso_com_dependencias(curso)
        _registrar_exclusao(request, "Curso", alvo_id, nome, empresa=empresa)
    messages.success(request, f"Curso {nome} excluido com sucesso.")
    return redirect("cursos_operacionais")


@staff_member_required
def conteudo_curso_operacional(request, curso_id):
    _exigir_editor_catalogo(request)
    if _empresa_contexto_obrigatoria(request) is None:
        return redirect("empresas_operacionais")
    curso = get_object_or_404(
        _cursos_contexto(request).select_related("produto"),
        pk=curso_id,
    )
    etapas = curso.etapas.prefetch_related("questoes__alternativas").order_by(
        "ordem",
        "id",
    )
    form_etapa = EtapaCursoForm()

    return render(
        request,
        "core/conteudo_curso_operacional.html",
        {"curso": curso, "etapas": etapas, "form_etapa": form_etapa},
    )


@staff_member_required
def criar_etapa_operacional(request, curso_id):
    _exigir_editor_catalogo(request)
    if _empresa_contexto_obrigatoria(request) is None:
        return redirect("empresas_operacionais")
    curso = get_object_or_404(_cursos_contexto(request), pk=curso_id)
    if request.method != "POST":
        return _redirect_conteudo_curso(curso.id, "nova-etapa")

    form = EtapaCursoForm(request.POST)
    if form.is_valid():
        etapa = form.save(commit=False)
        etapa.curso = curso
        etapa.save()
        registrar_evento(
            request.user,
            EventoAuditoria.Acao.CADASTRO,
            etapa,
            detalhes=f"Etapa criada no curso {curso.nome}.",
        )
        messages.success(request, f"Etapa {etapa.titulo} criada com sucesso.")
        return _redirect_conteudo_curso(curso.id, f"etapa-{etapa.id}")
    else:
        messages.error(request, "Nao foi possivel criar a etapa. Confira os dados.")
    return _redirect_conteudo_curso(curso.id, "nova-etapa")


@staff_member_required
def editar_etapa_operacional(request, etapa_id):
    _exigir_editor_catalogo(request)
    if _empresa_contexto_obrigatoria(request) is None:
        return redirect("empresas_operacionais")
    etapa = get_object_or_404(
        EtapaCurso.objects.select_related("curso").filter(
            curso__in=_cursos_contexto(request)
        ),
        pk=etapa_id,
    )
    if request.method == "POST":
        form = EtapaCursoForm(request.POST, instance=etapa)
        if form.is_valid():
            etapa = form.save()
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.EDICAO,
                etapa,
                detalhes=f"Etapa atualizada no curso {etapa.curso.nome}.",
            )
            messages.success(request, f"Etapa {etapa.titulo} atualizada com sucesso.")
            return _redirect_conteudo_curso(etapa.curso_id, f"etapa-{etapa.id}")
    else:
        form = EtapaCursoForm(instance=etapa)

    return render(
        request,
        "core/etapa_operacional_form.html",
        {"form": form, "etapa": etapa},
    )


@staff_member_required
@require_POST
def alternar_etapa_operacional(request, etapa_id):
    _exigir_editor_catalogo(request)
    if _empresa_contexto_obrigatoria(request) is None:
        return redirect("empresas_operacionais")
    etapa = get_object_or_404(
        EtapaCurso.objects.select_related("curso").filter(
            curso__in=_cursos_contexto(request)
        ),
        pk=etapa_id,
    )
    etapa.ativo = not etapa.ativo
    etapa.save(update_fields=["ativo"])
    registrar_evento(
        request.user,
        EventoAuditoria.Acao.STATUS,
        etapa,
        detalhes=f"Status da etapa no curso {etapa.curso.nome} alterado para {'ativa' if etapa.ativo else 'inativa'}.",
    )
    status = "ativada" if etapa.ativo else "desativada"
    messages.success(request, f"Etapa {status} com sucesso.")
    return _redirect_conteudo_curso(etapa.curso_id, f"etapa-{etapa.id}")


@staff_member_required
def criar_questao_operacional(request, etapa_id):
    _exigir_editor_catalogo(request)
    if _empresa_contexto_obrigatoria(request) is None:
        return redirect("empresas_operacionais")
    etapa = get_object_or_404(
        EtapaCurso.objects.select_related("curso").filter(
            curso__in=_cursos_contexto(request)
        ),
        pk=etapa_id,
    )
    if not etapa.avaliativa:
        messages.error(request, "Questoes so podem ser criadas em etapas avaliativas.")
        return _redirect_conteudo_curso(etapa.curso_id, f"etapa-{etapa.id}")
    if request.method != "POST":
        return _redirect_conteudo_curso(etapa.curso_id, f"etapa-{etapa.id}")

    form = QuestaoForm(request.POST)
    if form.is_valid():
        questao = form.save(commit=False)
        questao.etapa = etapa
        questao.save()
        registrar_evento(
            request.user,
            EventoAuditoria.Acao.CADASTRO,
            questao,
            detalhes=f"Questao criada na etapa {etapa.titulo}.",
        )
        messages.success(request, "Questao criada com sucesso.")
        return _redirect_conteudo_curso(etapa.curso_id, f"questao-{questao.id}")
    else:
        messages.error(request, "Nao foi possivel criar a questao. Confira os dados.")
    return _redirect_conteudo_curso(etapa.curso_id, f"etapa-{etapa.id}")


@staff_member_required
def editar_questao_operacional(request, questao_id):
    _exigir_editor_catalogo(request)
    if _empresa_contexto_obrigatoria(request) is None:
        return redirect("empresas_operacionais")
    questao = get_object_or_404(
        Questao.objects.select_related("etapa__curso").filter(
            etapa__curso__in=_cursos_contexto(request)
        ),
        pk=questao_id,
    )
    if request.method == "POST":
        form = QuestaoForm(request.POST, instance=questao)
        if form.is_valid():
            questao = form.save()
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.EDICAO,
                questao,
                detalhes=f"Questao atualizada na etapa {questao.etapa.titulo}.",
            )
            messages.success(request, "Questao atualizada com sucesso.")
            return _redirect_conteudo_curso(
                questao.etapa.curso_id, f"questao-{questao.id}"
            )
    else:
        form = QuestaoForm(instance=questao)

    return render(
        request,
        "core/questao_operacional_form.html",
        {"form": form, "questao": questao},
    )


@staff_member_required
@require_POST
def excluir_questao_operacional(request, questao_id):
    _exigir_editor_catalogo(request)
    if _empresa_contexto_obrigatoria(request) is None:
        return redirect("empresas_operacionais")
    questao = get_object_or_404(
        Questao.objects.select_related("etapa__curso").filter(
            etapa__curso__in=_cursos_contexto(request)
        ),
        pk=questao_id,
    )
    curso_id = questao.etapa.curso_id
    registrar_evento(
        request.user,
        EventoAuditoria.Acao.EDICAO,
        questao,
        detalhes=f"Questao removida da etapa {questao.etapa.titulo}.",
    )
    questao.delete()
    messages.success(request, "Questao removida com sucesso.")
    return _redirect_conteudo_curso(curso_id, f"etapa-{questao.etapa_id}")


@staff_member_required
def criar_alternativa_operacional(request, questao_id):
    _exigir_editor_catalogo(request)
    if _empresa_contexto_obrigatoria(request) is None:
        return redirect("empresas_operacionais")
    questao = get_object_or_404(
        Questao.objects.select_related("etapa__curso").filter(
            etapa__curso__in=_cursos_contexto(request)
        ),
        pk=questao_id,
    )
    if request.method != "POST":
        return _redirect_conteudo_curso(
            questao.etapa.curso_id, f"questao-{questao.id}"
        )

    form = AlternativaForm(request.POST)
    if form.is_valid():
        alternativa = form.save(commit=False)
        alternativa.questao = questao
        alternativa.save()
        registrar_evento(
            request.user,
            EventoAuditoria.Acao.CADASTRO,
            alternativa,
            detalhes=f"Alternativa criada na questao {questao.id}.",
        )
        messages.success(request, "Alternativa criada com sucesso.")
        return _redirect_conteudo_curso(
            questao.etapa.curso_id, f"questao-{questao.id}"
        )
    else:
        messages.error(
            request,
            "Nao foi possivel criar a alternativa. Confira os dados.",
        )
    return _redirect_conteudo_curso(questao.etapa.curso_id, f"questao-{questao.id}")


@staff_member_required
def editar_alternativa_operacional(request, alternativa_id):
    _exigir_editor_catalogo(request)
    if _empresa_contexto_obrigatoria(request) is None:
        return redirect("empresas_operacionais")
    alternativa = get_object_or_404(
        Alternativa.objects.select_related("questao__etapa__curso").filter(
            questao__etapa__curso__in=_cursos_contexto(request)
        ),
        pk=alternativa_id,
    )
    if request.method == "POST":
        form = AlternativaForm(request.POST, instance=alternativa)
        if form.is_valid():
            alternativa = form.save()
            registrar_evento(
                request.user,
                EventoAuditoria.Acao.EDICAO,
                alternativa,
                detalhes=f"Alternativa atualizada na questao {alternativa.questao_id}.",
            )
            messages.success(request, "Alternativa atualizada com sucesso.")
            return _redirect_conteudo_curso(
                alternativa.questao.etapa.curso_id,
                f"questao-{alternativa.questao_id}",
            )
    else:
        form = AlternativaForm(instance=alternativa)

    return render(
        request,
        "core/alternativa_operacional_form.html",
        {"form": form, "alternativa": alternativa},
    )


@staff_member_required
@require_POST
def excluir_alternativa_operacional(request, alternativa_id):
    _exigir_editor_catalogo(request)
    if _empresa_contexto_obrigatoria(request) is None:
        return redirect("empresas_operacionais")
    alternativa = get_object_or_404(
        Alternativa.objects.select_related("questao__etapa__curso").filter(
            questao__etapa__curso__in=_cursos_contexto(request)
        ),
        pk=alternativa_id,
    )
    curso_id = alternativa.questao.etapa.curso_id
    registrar_evento(
        request.user,
        EventoAuditoria.Acao.EDICAO,
        alternativa,
        detalhes=f"Alternativa removida da questao {alternativa.questao_id}.",
    )
    alternativa.delete()
    messages.success(request, "Alternativa removida com sucesso.")
    return _redirect_conteudo_curso(curso_id, f"questao-{alternativa.questao_id}")


def certificado_imprimir(request, codigo):
    conclusao, codigo_consultado = _buscar_conclusao_por_codigo(codigo)
    if not conclusao:
        return render(
            request,
            "core/certificado_imprimir.html",
            {"conclusao": None, "codigo_consultado": codigo_consultado or codigo},
            status=404,
        )

    situacao, status_classe = _situacao_certificado(conclusao)
    return render(
        request,
        "core/certificado_imprimir.html",
        {
            "conclusao": conclusao,
            "situacao": situacao,
            "status_classe": status_classe,
        },
    )


@login_required
def cursos_por_produto(request, produto_id):
    produto = get_object_or_404(
        Produto.objects.select_related("empresa"),
        id=produto_id,
        ativo=True,
    )
    tecnico = _tecnico_para_produto(request, produto)
    if not tecnico:
        messages.error(
            request,
            "Seu usuário não está vinculado a um técnico. Procure o administrador.",
        )
        return redirect("home")
    if tecnico.empresa_id != produto.empresa_id:
        messages.error(request, "Este produto não está liberado para o seu perfil.")
        return redirect("home")

    hoje = timezone.localdate()
    liberacoes = CursoLiberado.objects.filter(
        tecnico=tecnico, curso__produto=produto, curso__ativo=True, ativo=True
    ).select_related("curso")

    cursos_com_status = []
    for liberacao in liberacoes:
        curso = liberacao.curso
        ultima_conclusao = curso.conclusoes.filter(tecnico=tecnico).order_by(
            "-data_conclusao"
        ).first()
        progresso = curso.progressos.filter(tecnico=tecnico).first()

        _, _, situacao, status, status_classe = _situacao_liberacao(
            liberacao,
            hoje=hoje,
        )
        if situacao in {"vencido", "vence_30"}:
            status = "Reciclagem pendente"

        total = curso.etapas.filter(ativo=True).count()
        concluidas = 0
        if progresso:
            concluidas = progresso.etapas_concluidas.filter(
                tentativa=progresso.tentativa_atual, etapa__ativo=True
            ).count()
        percentual = round((concluidas / total) * 100) if total else 0

        cursos_com_status.append(
            {
                "curso": curso,
                "ultima_conclusao": ultima_conclusao,
                "status": status,
                "status_classe": status_classe,
                "percentual": percentual,
                "total_etapas": total,
            }
        )

    return render(
        request,
        "core/cursos_por_produto.html",
        {"produto": produto, "tecnico": tecnico, "cursos_com_status": cursos_com_status},
    )


@login_required
def curso_detalhe(request, curso_id, etapa_id=None):
    curso = get_object_or_404(
        Curso.objects.select_related("produto", "produto__empresa"),
        id=curso_id,
        ativo=True,
    )
    tecnico = _tecnico_para_curso(request, curso)
    if not tecnico or not _curso_liberado(tecnico, curso):
        messages.error(request, "Este curso não está liberado para o seu perfil.")
        return redirect("home")

    progresso, _ = ProgressoCurso.objects.get_or_create(
        tecnico=tecnico, curso=curso
    )
    ultima_conclusao = curso.conclusoes.filter(tecnico=tecnico).order_by(
        "-data_conclusao"
    ).first()
    conclusao_disponivel = ultima_conclusao
    if (
        progresso.status == ProgressoCurso.Status.APROVADO
        and ultima_conclusao
        and ultima_conclusao.data_vencimento < timezone.localdate()
    ):
        progresso.tentativa_atual += 1
        progresso.status = ProgressoCurso.Status.EM_ANDAMENTO
        progresso.iniciado_em = timezone.now()
        progresso.save(
            update_fields=[
                "tentativa_atual",
                "status",
                "iniciado_em",
                "atualizado_em",
            ]
        )
        conclusao_disponivel = None

    if not progresso.iniciado_em:
        progresso.iniciado_em = timezone.now()
        progresso.status = ProgressoCurso.Status.EM_ANDAMENTO
        progresso.save(update_fields=["iniciado_em", "status", "atualizado_em"])

    etapas, concluidas, primeira_pendente, itens = _contexto_etapas(curso, progresso)
    if not etapas:
        return render(
            request,
            "core/curso_detalhe.html",
            {"curso": curso, "tecnico": tecnico, "progresso": progresso, "itens": []},
        )

    etapa = (
        get_object_or_404(EtapaCurso, id=etapa_id, curso=curso, ativo=True)
        if etapa_id
        else primeira_pendente or etapas[-1]
    )
    if etapa.id not in concluidas and etapa != primeira_pendente:
        messages.warning(request, "Conclua as etapas anteriores para continuar.")
        return redirect(
            "curso_etapa", curso_id=curso.id, etapa_id=primeira_pendente.id
        )

    if request.method == "POST":
        if etapa.id in concluidas:
            return redirect("curso_etapa", curso_id=curso.id, etapa_id=etapa.id)

        if etapa.avaliativa:
            resultado = _corrigir_avaliacao(request, progresso, etapa, curso)
            if resultado:
                return resultado
        else:
            ProgressoEtapa.objects.create(
                progresso=progresso,
                etapa=etapa,
                tentativa=progresso.tentativa_atual,
            )

        return _avancar_ou_concluir(request, tecnico, curso, progresso)

    total = len(etapas)
    percentual = round((len(concluidas) / total) * 100) if total else 0
    return render(
        request,
        "core/curso_detalhe.html",
        {
            "curso": curso,
            "tecnico": tecnico,
            "progresso": progresso,
            "itens": itens,
            "etapa_atual": etapa,
            "etapa_concluida": etapa.id in concluidas,
            "conclusao_disponivel": conclusao_disponivel
            if progresso.status == ProgressoCurso.Status.APROVADO
            else None,
            "percentual": percentual,
        },
    )


@transaction.atomic
def _corrigir_avaliacao(request, progresso, etapa, curso):
    questoes = list(etapa.questoes.prefetch_related("alternativas"))
    if not questoes:
        messages.error(request, "Esta avaliação ainda não possui questões cadastradas.")
        return redirect("curso_etapa", curso_id=curso.id, etapa_id=etapa.id)

    acertos = 0
    for questao in questoes:
        alternativa_id = request.POST.get(f"questao_{questao.id}")
        if not alternativa_id:
            messages.error(request, "Responda todas as questões antes de enviar.")
            return redirect("curso_etapa", curso_id=curso.id, etapa_id=etapa.id)
        alternativa = get_object_or_404(
            Alternativa, id=alternativa_id, questao=questao
        )
        acertos += int(alternativa.correta)

    nota = (Decimal(acertos) / Decimal(len(questoes))) * Decimal("100")
    aprovado = nota >= curso.nota_minima
    TentativaAvaliacao.objects.create(
        progresso=progresso,
        etapa=etapa,
        numero_tentativa_curso=progresso.tentativa_atual,
        nota=nota,
        aprovado=aprovado,
    )

    if aprovado:
        ProgressoEtapa.objects.create(
            progresso=progresso,
            etapa=etapa,
            tentativa=progresso.tentativa_atual,
            nota=nota,
        )
        messages.success(request, f"Avaliação concluída com nota {nota:.0f}%.")
        return None

    progresso.status = ProgressoCurso.Status.REPROVADO
    progresso.save(update_fields=["status", "atualizado_em"])
    tentativa_reprovada = progresso.tentativa_atual
    progresso.tentativa_atual += 1
    progresso.status = ProgressoCurso.Status.EM_ANDAMENTO
    progresso.iniciado_em = timezone.now()
    progresso.save(
        update_fields=["tentativa_atual", "status", "iniciado_em", "atualizado_em"]
    )
    messages.error(
        request,
        (
            f"Nota {nota:.0f}%. O mínimo é {curso.nota_minima}%. "
            f"A tentativa {tentativa_reprovada} foi encerrada e o curso deve ser refeito."
        ),
    )
    primeira = curso.etapas.filter(ativo=True).first()
    return redirect("curso_etapa", curso_id=curso.id, etapa_id=primeira.id)


def _avancar_ou_concluir(request, tecnico, curso, progresso):
    etapas, concluidas, primeira_pendente, _ = _contexto_etapas(curso, progresso)
    if primeira_pendente:
        return redirect(
            "curso_etapa", curso_id=curso.id, etapa_id=primeira_pendente.id
        )

    if etapas and len(concluidas) == len(etapas):
        progresso.status = ProgressoCurso.Status.APROVADO
        progresso.save(update_fields=["status", "atualizado_em"])
        conclusao = ConclusaoTreinamento.objects.create(tecnico=tecnico, curso=curso)
        messages.success(
            request,
            "Parabéns! Curso concluído e certificação renovada com sucesso.",
        )
        return redirect("certificado_imprimir", codigo=conclusao.codigo_certificado)
    return redirect("cursos_por_produto", produto_id=curso.produto_id)
