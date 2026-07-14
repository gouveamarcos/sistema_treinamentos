# Produção

Este roteiro prepara a Academia Técnica para uma hospedagem mais robusta que o
MVP local ou PythonAnywhere.

## Variáveis obrigatórias

```text
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=troque-por-uma-chave-longa-unica-e-secreta
DJANGO_ALLOWED_HOSTS=treinamentos.suaempresa.com.br
DJANGO_CSRF_TRUSTED_ORIGINS=https://treinamentos.suaempresa.com.br
DATABASE_URL=postgres://usuario:senha@host:5432/sistema_treinamentos
```

Para PostgreSQL gerenciado, mantenha:

```text
DB_CONN_MAX_AGE=60
DB_SSLMODE=require
```

## Variáveis recomendadas

```text
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
SECURE_CONTENT_TYPE_NOSNIFF=True
SESSION_COOKIE_HTTPONLY=True
CSRF_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
CSRF_COOKIE_SAMESITE=Lax
X_FRAME_OPTIONS=DENY
MAX_CSV_IMPORT_SIZE_BYTES=2097152
```

Configure também SMTP:

```text
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.seudominio.com
EMAIL_PORT=587
EMAIL_HOST_USER=usuario
EMAIL_HOST_PASSWORD=senha
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=Academia Técnica <treinamentos@suaempresa.com.br>
```

## Comandos de release

Execute a cada publicação:

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy
```

Depois valide:

```bash
python manage.py test
```

## Processo web

O `Procfile` usa:

```text
web: gunicorn treinamentos.wsgi:application
```

Em hospedagens que não usam `Procfile`, configure o mesmo comando como processo
web principal.

## Saúde da aplicação

O endpoint público `/saude/` retorna:

```json
{"status": "ok", "database": "ok"}
```

Se o banco estiver indisponível, retorna HTTP 503. Use esse endpoint no monitor
da plataforma.

## Migração para PostgreSQL

1. Crie o banco PostgreSQL na hospedagem escolhida.
2. Configure `DATABASE_URL`.
3. Rode `python manage.py migrate --noinput`.
4. Crie ou redefina o administrador:

```bash
python manage.py redefinir_admin --username admin --email seu.email@empresa.com
```

5. Importe/cadastre empresas, técnicos, cursos e liberações pelo painel
operacional.

Para migrar dados reais do SQLite atual para PostgreSQL, exporte no ambiente
antigo antes de trocar `DATABASE_URL`:

```bash
python manage.py dumpdata --exclude auth.permission --exclude contenttypes --indent 2 > backup.json
```

Depois, no ambiente PostgreSQL já migrado:

```bash
python manage.py loaddata backup.json
```
