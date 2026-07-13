from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AlternativaForm,
    CursoForm,
    EmpresaForm,
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
    Produto,
    ProgressoCurso,
    ProgressoEtapa,
    Questao,
    ResponsavelEmpresa,
    Tecnico,
    TentativaAvaliacao,
)
from .scopes import empresas_do_usuario

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


def _responsaveis_visiveis(request):
    return ResponsavelEmpresa.objects.filter(
        empresa__in=empresas_do_usuario(request.user)
    ).select_related("empresa", "usuario")


def _empresas_visiveis(request):
    return empresas_do_usuario(request.user)


def _tecnicos_visiveis(request):
    return Tecnico.objects.filter(
        empresa__in=_empresas_visiveis(request)
    ).select_related("empresa", "usuario")


def _pode_gerenciar_catalogo(user):
    if user.is_superuser:
        return True
    return ResponsavelEmpresa.objects.filter(
        usuario=user,
        papel=ResponsavelEmpresa.Papel.EDITOR_CURSOS,
        ativo=True,
    ).exists()


def _exigir_editor_catalogo(request):
    if not _pode_gerenciar_catalogo(request.user):
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
    empresas = empresas_do_usuario(request.user).order_by("nome")

    liberacoes = CursoLiberado.objects.filter(
        ativo=True,
        tecnico__ativo=True,
        curso__ativo=True,
        tecnico__empresa__in=empresas,
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
            "empresas": empresas,
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
        form = LiberarCursoLoteForm(request.POST, usuario=request.user)
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
                initial={"empresa": form.cleaned_data["empresa"]},
                usuario=request.user,
            )
    else:
        form = LiberarCursoLoteForm(usuario=request.user)

    return render(
        request,
        "core/liberar_curso_lote.html",
        {"form": form, "resultado": resultado},
    )


@staff_member_required
def responsaveis_empresas(request):
    if request.method == "POST":
        form = ResponsavelEmpresaForm(request.POST, usuario=request.user)
        if form.is_valid():
            responsabilidade = form.save()
            messages.success(
                request,
                f"ResponsÃ¡vel {responsabilidade.usuario.email} salvo com sucesso.",
            )
            return redirect("responsaveis_empresas")
    else:
        form = ResponsavelEmpresaForm(usuario=request.user)

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
    responsabilidade = get_object_or_404(
        _responsaveis_visiveis(request),
        pk=responsavel_id,
    )
    if request.method == "POST":
        form = ResponsavelEmpresaForm(
            request.POST,
            usuario=request.user,
            instance=responsabilidade,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "ResponsÃ¡vel atualizado com sucesso.")
            return redirect("responsaveis_empresas")
    else:
        form = ResponsavelEmpresaForm(usuario=request.user, instance=responsabilidade)

    return render(
        request,
        "core/responsavel_empresa_form.html",
        {"form": form, "responsabilidade": responsabilidade},
    )


@staff_member_required
@require_POST
def alternar_responsavel_empresa(request, responsavel_id):
    responsabilidade = get_object_or_404(
        _responsaveis_visiveis(request),
        pk=responsavel_id,
    )
    responsabilidade.ativo = not responsabilidade.ativo
    responsabilidade.save()
    status = "ativado" if responsabilidade.ativo else "desativado"
    messages.success(request, f"ResponsÃ¡vel {status} com sucesso.")
    return redirect("responsaveis_empresas")


@staff_member_required
def empresas_operacionais(request):
    pode_criar = request.user.is_superuser
    if request.method == "POST":
        if not pode_criar:
            raise PermissionDenied
        form = EmpresaForm(request.POST)
        if form.is_valid():
            empresa = form.save()
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
def editar_empresa_operacional(request, empresa_id):
    empresa = get_object_or_404(_empresas_visiveis(request), pk=empresa_id)
    if request.method == "POST":
        form = EmpresaForm(request.POST, instance=empresa)
        if form.is_valid():
            empresa = form.save()
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
    if not request.user.is_superuser:
        raise PermissionDenied
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    empresa.ativa = not empresa.ativa
    empresa.save(update_fields=["ativa"])
    status = "ativada" if empresa.ativa else "desativada"
    messages.success(request, f"Empresa {status} com sucesso.")
    return redirect("empresas_operacionais")


@staff_member_required
def tecnicos_operacionais(request):
    if request.method == "POST":
        form = TecnicoForm(request.POST, usuario=request.user)
        if form.is_valid():
            tecnico = form.save()
            messages.success(request, f"Tecnico {tecnico.nome} salvo com sucesso.")
            return redirect("tecnicos_operacionais")
    else:
        form = TecnicoForm(usuario=request.user)

    tecnicos = _tecnicos_visiveis(request).order_by("empresa__nome", "nome")
    return render(
        request,
        "core/tecnicos_operacionais.html",
        {"form": form, "tecnicos": tecnicos},
    )


@staff_member_required
def editar_tecnico_operacional(request, tecnico_id):
    tecnico = get_object_or_404(_tecnicos_visiveis(request), pk=tecnico_id)
    if request.method == "POST":
        form = TecnicoForm(request.POST, usuario=request.user, instance=tecnico)
        if form.is_valid():
            tecnico = form.save()
            messages.success(request, f"Tecnico {tecnico.nome} atualizado com sucesso.")
            return redirect("tecnicos_operacionais")
    else:
        form = TecnicoForm(usuario=request.user, instance=tecnico)

    return render(
        request,
        "core/tecnico_operacional_form.html",
        {"form": form, "tecnico": tecnico},
    )


@staff_member_required
@require_POST
def alternar_tecnico_operacional(request, tecnico_id):
    tecnico = get_object_or_404(_tecnicos_visiveis(request), pk=tecnico_id)
    tecnico.ativo = not tecnico.ativo
    tecnico.save(update_fields=["ativo"])
    status = "ativado" if tecnico.ativo else "desativado"
    messages.success(request, f"Tecnico {status} com sucesso.")
    return redirect("tecnicos_operacionais")


@staff_member_required
def produtos_operacionais(request):
    _exigir_editor_catalogo(request)
    if request.method == "POST":
        form = ProdutoForm(request.POST)
        if form.is_valid():
            produto = form.save()
            messages.success(request, f"Produto {produto.nome} salvo com sucesso.")
            return redirect("produtos_operacionais")
    else:
        form = ProdutoForm()

    produtos = Produto.objects.order_by("nome")
    return render(
        request,
        "core/produtos_operacionais.html",
        {"form": form, "produtos": produtos},
    )


@staff_member_required
def editar_produto_operacional(request, produto_id):
    _exigir_editor_catalogo(request)
    produto = get_object_or_404(Produto, pk=produto_id)
    if request.method == "POST":
        form = ProdutoForm(request.POST, instance=produto)
        if form.is_valid():
            produto = form.save()
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
    produto = get_object_or_404(Produto, pk=produto_id)
    produto.ativo = not produto.ativo
    produto.save(update_fields=["ativo"])
    status = "ativado" if produto.ativo else "desativado"
    messages.success(request, f"Produto {status} com sucesso.")
    return redirect("produtos_operacionais")


@staff_member_required
def cursos_operacionais(request):
    _exigir_editor_catalogo(request)
    if request.method == "POST":
        form = CursoForm(request.POST)
        if form.is_valid():
            curso = form.save()
            messages.success(request, f"Curso {curso.nome} salvo com sucesso.")
            return redirect("cursos_operacionais")
    else:
        form = CursoForm()

    cursos = Curso.objects.select_related("produto").order_by("produto__nome", "nome")
    return render(
        request,
        "core/cursos_operacionais.html",
        {"form": form, "cursos": cursos},
    )


@staff_member_required
def editar_curso_operacional(request, curso_id):
    _exigir_editor_catalogo(request)
    curso = get_object_or_404(Curso.objects.select_related("produto"), pk=curso_id)
    if request.method == "POST":
        form = CursoForm(request.POST, instance=curso)
        if form.is_valid():
            curso = form.save()
            messages.success(request, f"Curso {curso.nome} atualizado com sucesso.")
            return redirect("cursos_operacionais")
    else:
        form = CursoForm(instance=curso)

    return render(
        request,
        "core/curso_operacional_form.html",
        {"form": form, "curso": curso},
    )


@staff_member_required
@require_POST
def alternar_curso_operacional(request, curso_id):
    _exigir_editor_catalogo(request)
    curso = get_object_or_404(Curso, pk=curso_id)
    curso.ativo = not curso.ativo
    curso.save(update_fields=["ativo"])
    status = "ativado" if curso.ativo else "desativado"
    messages.success(request, f"Curso {status} com sucesso.")
    return redirect("cursos_operacionais")


@staff_member_required
def conteudo_curso_operacional(request, curso_id):
    _exigir_editor_catalogo(request)
    curso = get_object_or_404(Curso.objects.select_related("produto"), pk=curso_id)
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
    curso = get_object_or_404(Curso, pk=curso_id)
    if request.method != "POST":
        return redirect("conteudo_curso_operacional", curso_id=curso.id)

    form = EtapaCursoForm(request.POST)
    if form.is_valid():
        etapa = form.save(commit=False)
        etapa.curso = curso
        etapa.save()
        messages.success(request, f"Etapa {etapa.titulo} criada com sucesso.")
    else:
        messages.error(request, "Nao foi possivel criar a etapa. Confira os dados.")
    return redirect("conteudo_curso_operacional", curso_id=curso.id)


@staff_member_required
def editar_etapa_operacional(request, etapa_id):
    _exigir_editor_catalogo(request)
    etapa = get_object_or_404(EtapaCurso.objects.select_related("curso"), pk=etapa_id)
    if request.method == "POST":
        form = EtapaCursoForm(request.POST, instance=etapa)
        if form.is_valid():
            etapa = form.save()
            messages.success(request, f"Etapa {etapa.titulo} atualizada com sucesso.")
            return redirect("conteudo_curso_operacional", curso_id=etapa.curso_id)
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
    etapa = get_object_or_404(EtapaCurso.objects.select_related("curso"), pk=etapa_id)
    etapa.ativo = not etapa.ativo
    etapa.save(update_fields=["ativo"])
    status = "ativada" if etapa.ativo else "desativada"
    messages.success(request, f"Etapa {status} com sucesso.")
    return redirect("conteudo_curso_operacional", curso_id=etapa.curso_id)


@staff_member_required
def criar_questao_operacional(request, etapa_id):
    _exigir_editor_catalogo(request)
    etapa = get_object_or_404(EtapaCurso.objects.select_related("curso"), pk=etapa_id)
    if not etapa.avaliativa:
        messages.error(request, "Questoes so podem ser criadas em etapas avaliativas.")
        return redirect("conteudo_curso_operacional", curso_id=etapa.curso_id)
    if request.method != "POST":
        return redirect("conteudo_curso_operacional", curso_id=etapa.curso_id)

    form = QuestaoForm(request.POST)
    if form.is_valid():
        questao = form.save(commit=False)
        questao.etapa = etapa
        questao.save()
        messages.success(request, "Questao criada com sucesso.")
    else:
        messages.error(request, "Nao foi possivel criar a questao. Confira os dados.")
    return redirect("conteudo_curso_operacional", curso_id=etapa.curso_id)


@staff_member_required
def editar_questao_operacional(request, questao_id):
    _exigir_editor_catalogo(request)
    questao = get_object_or_404(
        Questao.objects.select_related("etapa__curso"),
        pk=questao_id,
    )
    if request.method == "POST":
        form = QuestaoForm(request.POST, instance=questao)
        if form.is_valid():
            form.save()
            messages.success(request, "Questao atualizada com sucesso.")
            return redirect(
                "conteudo_curso_operacional",
                curso_id=questao.etapa.curso_id,
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
    questao = get_object_or_404(
        Questao.objects.select_related("etapa__curso"),
        pk=questao_id,
    )
    curso_id = questao.etapa.curso_id
    questao.delete()
    messages.success(request, "Questao removida com sucesso.")
    return redirect("conteudo_curso_operacional", curso_id=curso_id)


@staff_member_required
def criar_alternativa_operacional(request, questao_id):
    _exigir_editor_catalogo(request)
    questao = get_object_or_404(
        Questao.objects.select_related("etapa__curso"),
        pk=questao_id,
    )
    if request.method != "POST":
        return redirect("conteudo_curso_operacional", curso_id=questao.etapa.curso_id)

    form = AlternativaForm(request.POST)
    if form.is_valid():
        alternativa = form.save(commit=False)
        alternativa.questao = questao
        alternativa.save()
        messages.success(request, "Alternativa criada com sucesso.")
    else:
        messages.error(
            request,
            "Nao foi possivel criar a alternativa. Confira os dados.",
        )
    return redirect("conteudo_curso_operacional", curso_id=questao.etapa.curso_id)


@staff_member_required
def editar_alternativa_operacional(request, alternativa_id):
    _exigir_editor_catalogo(request)
    alternativa = get_object_or_404(
        Alternativa.objects.select_related("questao__etapa__curso"),
        pk=alternativa_id,
    )
    if request.method == "POST":
        form = AlternativaForm(request.POST, instance=alternativa)
        if form.is_valid():
            form.save()
            messages.success(request, "Alternativa atualizada com sucesso.")
            return redirect(
                "conteudo_curso_operacional",
                curso_id=alternativa.questao.etapa.curso_id,
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
    alternativa = get_object_or_404(
        Alternativa.objects.select_related("questao__etapa__curso"),
        pk=alternativa_id,
    )
    curso_id = alternativa.questao.etapa.curso_id
    alternativa.delete()
    messages.success(request, "Alternativa removida com sucesso.")
    return redirect("conteudo_curso_operacional", curso_id=curso_id)


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
