from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import PrimeiroAcessoForm
from .models import (
    Alternativa,
    ConclusaoTreinamento,
    Curso,
    CursoLiberado,
    EtapaCurso,
    Produto,
    ProgressoCurso,
    ProgressoEtapa,
    Tecnico,
    TentativaAvaliacao,
)


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

        if ultima_conclusao and ultima_conclusao.data_vencimento >= hoje:
            status, status_classe = "Em dia", "status-em-dia"
        elif ultima_conclusao:
            status, status_classe = "Reciclagem pendente", "status-vencido"
        elif progresso and progresso.status == ProgressoCurso.Status.EM_ANDAMENTO:
            status, status_classe = "Em andamento", "status-andamento"
        else:
            status, status_classe = "Pendente", "status-pendente"

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
