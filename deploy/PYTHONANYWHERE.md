# Publicação no PythonAnywhere

Este roteiro está personalizado para o usuário PythonAnywhere `marcosgouvea`.

## 1. Enviar o projeto

Envie a pasta do projeto para:

```text
/home/marcosgouvea/sistema_treinamentos
```

Não envie a pasta `venv`. Crie um ambiente virtual novo no servidor.

## 2. Criar o ambiente virtual

Na aba **Consoles**, abra um console Bash. Escolha uma versão de Python
disponível no PythonAnywhere e compatível com o `requirements.txt`. Use a mesma
versão ao criar a aplicação web.

```bash
cd /home/marcosgouvea/sistema_treinamentos
python3 -m venv ~/.virtualenvs/academia-tecnica
source ~/.virtualenvs/academia-tecnica/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Preparar banco e arquivos estáticos

```bash
cd /home/marcosgouvea/sistema_treinamentos
source ~/.virtualenvs/academia-tecnica/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
python manage.py criar_cursos_demonstracao --sem-tecnico
python manage.py check
```

O comando acima cria os quatro produtos e cursos, mas não cria o técnico de
demonstração. Não o execute novamente depois de cadastrar técnicos reais, pois
ele apaga os dados de negócio antes de recriar o catálogo.

## 4. Criar a aplicação web

Na aba **Web**:

1. Clique em **Add a new web app**.
2. Escolha **Manual configuration**.
3. Escolha a mesma versão de Python do ambiente virtual.
4. Em **Virtualenv**, informe:

```text
/home/marcosgouvea/.virtualenvs/academia-tecnica
```

## 5. Configurar o WSGI

Abra o arquivo WSGI indicado na aba **Web** e use como base:

```text
deploy/pythonanywhere_wsgi.py.example
```

Defina uma chave secreta longa e substitua o campo da senha de app do Google.
Não publique essas credenciais em repositórios.

## 6. Configurar arquivos estáticos

Na seção **Static files** da aba **Web**, adicione:

```text
URL:  /static/
Path: /home/marcosgouvea/sistema_treinamentos/staticfiles
```

O vídeo demonstrativo também será servido por esse mapeamento.

## 7. Publicar

Clique em **Reload** na aba **Web** e acesse:

```text
https://marcosgouvea.pythonanywhere.com
```

Depois entre em `/admin/`, cadastre os técnicos e libere os cursos.

## 8. Primeiro acesso dos técnicos

Para cada técnico, envie manualmente:

- endereço da plataforma;
- e-mail cadastrado;
- matrícula cadastrada;
- instrução para clicar em **Primeiro acesso**.

O técnico usará o e-mail como usuário e criará a própria senha.

## 9. Recuperação de senha

O arquivo WSGI está preparado para `smtp.gmail.com`, porta `587`, TLS e o e-mail
`gouvea.marcos@gmail.com`.

Ative a verificação em duas etapas na conta Google e gere uma senha de app em:

```text
https://myaccount.google.com/apppasswords
```

Cole a senha de app somente no arquivo WSGI do PythonAnywhere. Não use a senha
normal do Gmail e não envie a senha de app por mensagem.

Se a conta gratuita bloquear a conexão SMTP, manteremos o fluxo implementado e
usaremos convite e recuperação assistidos durante a demonstração, ou migraremos
o envio para um serviço HTTP permitido.

Após configurar o SMTP no WSGI, clique em **Reload** e teste com uma conta de
técnico antes da apresentação.

## Atualizações futuras

Quando alterar CSS, templates ou vídeos:

```bash
cd /home/marcosgouvea/sistema_treinamentos
source ~/.virtualenvs/academia-tecnica/bin/activate
python manage.py collectstatic --noinput
```

Depois clique em **Reload** na aba **Web**.
