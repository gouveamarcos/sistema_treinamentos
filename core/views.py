from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import LiberarCursoLoteForm, PrimeiroAcessoForm, ValidarCertificadoForm
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
    Tecnico,
    TentativaAvaliacao,
)

JANELA_VENCIMENTO_DIAS = 30


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


def _curso_liberado(tecnico, curso):
    return CursoLiberado.objects.filter(
        tecnico=tecnico, curso=curso, curso__ativo=True, ativo=True
    ).exists()


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
    produtos = Produto.objects.filter(
        ativo=True,
        cursos__ativo=True,
        cursos__liberacoes__tecnico__usuario=request.user,
        cursos__liberacoes__ativo=True,
    ).distinct().order_by("nome")
    return render(request, "core/home.html", {"produtos": produtos})


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
    empresa_id = request.GET.get("empresa") or ""
    situacao_filtro = request.GET.get("situacao") or ""
    hoje = timezone.localdate()

    liberacoes = CursoLiberado.objects.filter(
        ativo=True,
        tecnico__ativo=True,
        curso__ativo=True,
    ).select_related("tecnico__empresa", "curso__produto")

    if empresa_id:
        liberacoes = liberacoes.filter(tecnico__empresa_id=empresa_id)

    itens = []
    totais = {
        "total": 0,
        "pendente": 0,
        "em_andamento": 0,
        "em_dia": 0,
        "vence_30": 0,
        "vencido": 0,
        "sem_vencimento": 0,
    }

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

        totais["total"] += 1
        totais[situacao] += 1
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

    return render(
        request,
        "core/relatorio_treinamentos.html",
        {
            "empresas": Empresa.objects.filter(ativa=True).order_by("nome"),
            "empresa_id": empresa_id,
            "situacao_filtro": situacao_filtro,
            "itens": itens,
            "totais": totais,
        },
    )


@staff_member_required
@transaction.atomic
def liberar_curso_lote(request):
    resultado = None
    if request.method == "POST":
        form = LiberarCursoLoteForm(request.POST)
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
            form = LiberarCursoLoteForm(
                initial={"empresa": form.cleaned_data["empresa"]}
            )
    else:
        form = LiberarCursoLoteForm()

    return render(
        request,
        "core/liberar_curso_lote.html",
        {"form": form, "resultado": resultado},
    )


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
    produto = get_object_or_404(Produto, id=produto_id, ativo=True)
    tecnico = _tecnico_logado(request)
    if not tecnico:
        messages.error(
            request,
            "Seu usuário não está vinculado a um técnico. Procure o administrador.",
        )
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
        Curso.objects.select_related("produto"), id=curso_id, ativo=True
    )
    tecnico = _tecnico_logado(request)
    if not tecnico or not _curso_liberado(tecnico, curso):
        messages.error(request, "Este curso não está liberado para o seu perfil.")
        return redirect("home")

    progresso, _ = ProgressoCurso.objects.get_or_create(
        tecnico=tecnico, curso=curso
    )
    ultima_conclusao = curso.conclusoes.filter(tecnico=tecnico).order_by(
        "-data_conclusao"
    ).first()
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
        ConclusaoTreinamento.objects.create(tecnico=tecnico, curso=curso)
        messages.success(
            request,
            "Parabéns! Curso concluído e certificação renovada com sucesso.",
        )
    return redirect("cursos_por_produto", produto_id=curso.produto_id)
