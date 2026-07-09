# Academia Técnica Sem Parar

Plataforma Django para treinamento, avaliação e reciclagem periódica de técnicos.

## Recursos disponíveis

- Cadastro de técnicos e ativação no primeiro acesso.
- Cadastro de empresas/clientes e vínculo dos técnicos à empresa.
- Cadastro de responsáveis por empresa com papéis operacionais e de edição.
- Recuperação de senha por link temporário enviado por e-mail.
- Cursos separados por produto.
- Liberação individual de cursos.
- Ações em lote no admin para ativar, inativar e classificar liberações.
- Etapas ordenadas em texto, vídeo, teste e prova.
- Bloqueio de etapas futuras até a conclusão das anteriores.
- Nota mínima configurável por curso.
- Reinício obrigatório do curso após reprovação.
- Certificação com data de vencimento.
- Código único de certificado para cada conclusão.
- Nova tentativa automática quando a certificação vence.
- Lembretes de reciclagem por e-mail.
- Filtros operacionais para certificações vencidas ou próximas do vencimento.

## Executar localmente

```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py runserver
```

Acesse `http://127.0.0.1:8000/`.

## Cadastrar conteúdo

No painel `/admin/`:

1. Cadastre empresas/clientes.
2. Cadastre técnicos vinculados à empresa correta.
3. Cadastre responsáveis por empresa quando outras pessoas forem apoiar a gestão.
4. Cadastre os produtos e cursos.
5. Dentro do curso, crie as etapas na ordem desejada.
6. Para testes e provas, cadastre questões e suas alternativas.
7. Marque somente a alternativa correta de cada questão.
8. Libere o curso para os técnicos em **Cursos liberados**.

Responsáveis ativos recebem automaticamente um grupo de permissões conforme o
papel cadastrado: **Responsável operacional** ou **Editor de cursos**.

Em **Cursos liberados**, use as ações em lote do admin para ativar/inativar
liberações ou marcar cursos como obrigatórios/opcionais. Em **Conclusões de
treinamento**, use o filtro de situação para encontrar certificados vencidos,
próximos do vencimento ou em dia.

URLs de vídeo devem ser próprias para incorporação, como
`https://www.youtube.com/embed/ID_DO_VIDEO`.

## Redefinir acesso administrativo

Se perder o acesso ao painel `/admin/`, redefina ou recrie o administrador:

```powershell
.\venv\Scripts\python.exe manage.py redefinir_admin --username admin --email seu.email@empresa.com
```

O comando solicita a nova senha no terminal sem exibi-la na tela. Em automações
seguras, também é possível informar `--password` junto com `--noinput`.

## Lembretes por e-mail

O comando abaixo avisa sobre certificações vencidas ou que vencem em até 30 dias:

```powershell
.\venv\Scripts\python.exe manage.py enviar_lembretes_reciclagem
```

Altere a janela com `--dias 15`. Em produção, agende o comando diariamente pelo
Agendador de Tarefas do Windows, cron ou serviço equivalente.

Configure SMTP pelas variáveis `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` e `DEFAULT_FROM_EMAIL`.

## PythonAnywhere

O roteiro completo para publicação está em
[`deploy/PYTHONANYWHERE.md`](deploy/PYTHONANYWHERE.md).

Para criar o catálogo no servidor sem gerar o técnico demonstrativo:

```bash
python manage.py criar_cursos_demonstracao --sem-tecnico
```

## Produção

Defina ao menos:

```text
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=uma-chave-longa-e-secreta
DJANGO_ALLOWED_HOSTS=treinamentos.suaempresa.com.br
```
