# Manual 4 — Plataforma no Ubuntu Server

Academia Técnica · Edição de 08/09/2026 · Ubuntu Server 24.04 LTS, x64.

**Objetivo:** colocar a plataforma na internet com PostgreSQL local, Gunicorn, Caddy e HTTPS; iniciar automaticamente; configurar e-mail e backup. Este roteiro mantém o código e as regras de acesso do projeto. Tempo de trabalho estimado: meio período, além das liberações de rede e testes da empresa.

## 1. Antes de executar

Conclua [PostgreSQL no Ubuntu](03_POSTGRESQL_UBUNTU.md) e a ficha de rede de [Comece aqui](00_LEIA_PRIMEIRO.md). É necessário ter:

- Ubuntu 24.04 atualizado, conta com `sudo` e IP interno fixo.
- Banco `sistema_treinamentos`, usuário `academia_app` e sua senha.
- Subdomínio real, DNS e encaminhamento TCP 80/443 preparados pela TI.
- Credenciais de SMTP autenticado com STARTTLS/587 e remetente autorizado.
- Pacote do projeto contendo `manage.py`, `requirements.txt`, `core` e `treinamentos`.

Os exemplos usam `treinamentos.suaempresa.com.br`. Substitua esse nome em **todos** os arquivos e testes pelo domínio real. Não substitua os nomes das pastas, serviços ou banco deste roteiro sem adaptar as demais etapas.

Entre por console/SSH como explicado no manual do banco. Todos os blocos abaixo são para o terminal Ubuntu. O sistema operacional já deve estar instalado; não formate a máquina para seguir este manual.

## 2. Instalar Python e Caddy

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv cron curl ca-certificates gnupg debian-keyring debian-archive-keyring apt-transport-https
python3.12 --version
```

Espere `Python 3.12.x`. Django 6.0 exige Python 3.12, 3.13 ou 3.14. [Fonte: compatibilidade Django](https://docs.djangoproject.com/en/6.0/faq/install/).

Instale Caddy pelo repositório estável oficial. Se Caddy já estiver instalado, não sobrescreva sua configuração; confirme com a TI se ele atende outro sistema.

```bash
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
sudo chmod o+r /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
caddy version
```

Não prossiga se o download da chave falhar. Proxy corporativo pode exigir configuração pela TI. [Fonte: instalação Caddy](https://caddyserver.com/docs/install).

## 3. Criar as pastas e copiar o projeto

Crie uma conta técnica sem login interativo e as pastas:

```bash
sudo useradd --system --user-group --home-dir /srv/academia --shell /usr/sbin/nologin academia
sudo install -d -m 755 /srv/academia /srv/academia/app
sudo install -d -m 750 -o root -g academia /etc/academia
```

Se a conta já existir, confirme que é desta instalação; não a recrie. `/srv/academia/app` conterá o código, `/srv/academia/venv` as bibliotecas e `/etc/academia` a configuração.

Na máquina de origem, prepare uma pasta de entrega apenas com os arquivos do projeto. Não inclua `venv`, `.venv`, `.git`, `.env`, `__pycache__` nem `db.sqlite3`. Banco antigo e `media` devem ser transferidos conscientemente conforme [Transferir dados](05_TRANSFERIR_DADOS_EXISTENTES.md).

Uma forma simples de copiar é usar um cliente SFTP aprovado pela TI: informe IP do servidor, usuário SSH e autenticação; crie `entrega-academia` na pasta pessoal desse usuário e envie os arquivos. `manage.py` deve ficar diretamente dentro de `entrega-academia`, não dentro de uma segunda pasta do mesmo nome.

No servidor, troque `SEU_USUARIO` pelo login utilizado:

```bash
ls -l /home/SEU_USUARIO/entrega-academia/manage.py
sudo cp -a /home/SEU_USUARIO/entrega-academia/. /srv/academia/app/
sudo chown -R root:root /srv/academia/app
sudo chmod -R u=rwX,go=rX /srv/academia/app
ls -l /srv/academia/app/manage.py /srv/academia/app/requirements.txt
```

O comando de cópia é para a **primeira instalação**, em pasta vazia. A seção de atualização explica como tratar futuras versões. O serviço poderá ler o código, mas não precisa alterá-lo.

## 4. Instalar as bibliotecas

```bash
sudo python3.12 -m venv /srv/academia/venv
sudo /srv/academia/venv/bin/python -m pip install --upgrade pip
sudo /srv/academia/venv/bin/python -m pip install -r /srv/academia/app/requirements.txt
sudo /srv/academia/venv/bin/python -m pip check
sudo /srv/academia/venv/bin/python -m django --version
```

Espere `No broken requirements found` e a versão definida no projeto (`6.0.5` nesta edição). Não instale Django separadamente em outra versão. Guarde o inventário instalado:

```bash
sudo /srv/academia/venv/bin/python -m pip freeze | sudo tee /etc/academia/bibliotecas-instaladas.txt > /dev/null
sudo install -d -o academia -g caddy -m 2750 /srv/academia/app/media /srv/academia/app/staticfiles
```

Essas duas pastas precisam ser graváveis pela aplicação e legíveis pelo Caddy. Elas são as únicas pastas do projeto que este roteiro torna graváveis pelo serviço.

## 5. Criar a configuração persistente

**O projeto não lê `.env` sozinho.** Este roteiro carrega o arquivo explicitamente no serviço e nos comandos administrativos. Não basta copiar `.env.example`.

Gere a chave do Django:

```bash
/srv/academia/venv/bin/python -c 'import secrets; print(secrets.token_hex(32))'
sudo nano /etc/academia/academia.env
```

Copie a chave gerada para o campo correspondente. Cole o modelo completo abaixo e preencha os campos `SUBSTITUA`. Use uma linha por variável, sem espaços ao redor de `=`. Preserve as aspas simples. Para valores que contenham uma aspa simples, peça à TI para adaptar a representação tanto para Bash quanto para `EnvironmentFile`; a senha alfanumérica do banco evita esse caso.

```text
DJANGO_DEBUG='False'
DJANGO_SECRET_KEY='SUBSTITUA_PELA_CHAVE_GERADA'
DJANGO_ALLOWED_HOSTS='treinamentos.suaempresa.com.br,127.0.0.1,localhost'
DJANGO_CSRF_TRUSTED_ORIGINS='https://treinamentos.suaempresa.com.br'
DATABASE_URL='postgresql://academia_app:SUBSTITUA_SENHA_ALFANUMERICA@127.0.0.1:5432/sistema_treinamentos'
DB_SSLMODE='disable'
DB_CONN_MAX_AGE='60'
USE_X_FORWARDED_PROTO='True'
SECURE_SSL_REDIRECT='True'
SESSION_COOKIE_SECURE='True'
CSRF_COOKIE_SECURE='True'
SECURE_HSTS_SECONDS='0'
SECURE_HSTS_INCLUDE_SUBDOMAINS='False'
SECURE_HSTS_PRELOAD='False'
EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST='SUBSTITUA_SERVIDOR_SMTP'
EMAIL_PORT='587'
EMAIL_HOST_USER='SUBSTITUA_USUARIO_SMTP'
EMAIL_HOST_PASSWORD='SUBSTITUA_SENHA_SMTP'
EMAIL_USE_TLS='True'
EMAIL_TIMEOUT='20'
DEFAULT_FROM_EMAIL='Academia Tecnica <SUBSTITUA_EMAIL_REMETENTE>'
PASSWORD_RESET_TIMEOUT='604800'
MAX_CSV_IMPORT_SIZE_BYTES='2097152'
PYTHONUNBUFFERED='1'
PYTHONDONTWRITEBYTECODE='1'
```

`ALLOWED_HOSTS` contém nomes, sem `https://`; `CSRF_TRUSTED_ORIGINS` contém endereços com `https://`. A senha do banco deve ser a mesma testada no manual PostgreSQL. Se optar por senha com símbolos, a parte de senha na URL precisa ser codificada com percent-encoding; não coloque `@`, `#`, `/` ou `:` crus na URL. O aplicativo não interpreta `?sslmode=...` nesta configuração; use **DB_SSLMODE**.

O servidor de e-mail deve aceitar o método implementado: usuário/senha com STARTTLS. Se a empresa exigir OAuth ou somente SMTPS/465, peça à TI um relay compatível; não troque só o número da porta. Não use as contas de demonstração do `.env.example`.

Salve no Nano e proteja o arquivo:

```bash
sudo chown root:academia /etc/academia/academia.env
sudo chmod 640 /etc/academia/academia.env
```

## 6. Criar o comando administrativo

Esse pequeno auxiliar fica fora do código do projeto e garante que migrações, e-mails e administração usem o mesmo banco do serviço.

```bash
sudo nano /usr/local/sbin/academia-manage
```

Conteúdo completo:

```bash
#!/bin/bash
set -euo pipefail
set -a
source /etc/academia/academia.env
set +a
cd /srv/academia/app
umask 0027
exec runuser -u academia -- /srv/academia/venv/bin/python manage.py "$@"
```

Salve; depois:

```bash
sudo chown root:root /usr/local/sbin/academia-manage
sudo chmod 750 /usr/local/sbin/academia-manage
sudo academia-manage shell -c "from django.db import connection; connection.ensure_connection(); print(connection.vendor, connection.settings_dict['NAME'])"
```

**Resultado obrigatório:** `postgresql sistema_treinamentos`. Se aparecer `sqlite`, pare: a variável do banco não foi carregada. Não continue com migrações no banco errado.

## 7. Preparar tabelas e administrador

Para instalação vazia:

```bash
sudo academia-manage migrate --noinput
sudo academia-manage showmigrations
sudo academia-manage collectstatic --noinput
sudo academia-manage createsuperuser
sudo academia-manage check --deploy
```

As migrações devem aparecer marcadas com `[X]`. `collectstatic` reúne CSS e vídeos locais em `staticfiles`. `createsuperuser` pede nome de usuário, e-mail e senha do administrador do site. Anote o usuário e guarde a senha no cofre. O administrador do site é diferente de `postgres` e `academia_app`.

Durante a montagem haverá avisos relacionados ao HSTS porque foi definido como zero e sem preload. A seção de HTTPS explica a ativação após o teste. Outros erros/avisos devem ser entendidos, não ignorados. Não execute `manage.py test` neste banco de produção; testes exigem banco separado e outras permissões.

Se for trazer dados antigos, faça a migração de dados do apêndice depois de `migrate` e **antes** de criar usuários/cadastros novos, para evitar colisões.

## 8. Criar o serviço da plataforma

```bash
sudo nano /etc/systemd/system/academia.service
```

Cole:

```ini
[Unit]
Description=Academia Tecnica - Django Gunicorn
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=academia
Group=academia
WorkingDirectory=/srv/academia/app
EnvironmentFile=/etc/academia/academia.env
ExecStart=/srv/academia/venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 2 --timeout 120 --access-logfile - --error-logfile - treinamentos.wsgi:application
Restart=on-failure
RestartSec=5
UMask=0027
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Salve e execute:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now academia
sudo systemctl status academia --no-pager
curl -i -H 'X-Forwarded-Proto: https' http://127.0.0.1:8000/saude/
```

Espere serviço `active (running)` e HTTP 200 com `{"status": "ok", "database": "ok"}`. O cabeçalho usado no teste local representa o proxy HTTPS. Sem ele, um redirecionamento para HTTPS é esperado. **Não publique a porta 8000.** Os dois workers são um ponto inicial, a ajustar após monitorar o uso real. [Fonte: Gunicorn](https://docs.gunicorn.org/en/stable/settings.html).

## 9. Configurar endereço, arquivos e HTTPS

No servidor dedicado, preserve uma cópia da configuração original do Caddy:

```bash
sudo cp -n /etc/caddy/Caddyfile /etc/caddy/Caddyfile.antes-academia
sudo nano /etc/caddy/Caddyfile
```

Substitua o conteúdo pelo bloco abaixo, trocando domínio e e-mail reais:

```caddyfile
{
    email SUBSTITUA_EMAIL_DA_TI
}

treinamentos.suaempresa.com.br {
    encode zstd gzip
    header X-Content-Type-Options nosniff
    handle_path /static/* {
        root * /srv/academia/app/staticfiles
        file_server
    }
    handle_path /media/* {
        root * /srv/academia/app/media
        file_server
    }
    handle {
        reverse_proxy 127.0.0.1:8000 {
            header_up X-Forwarded-Proto {scheme}
        }
    }
    log {
        output file /var/log/caddy/academia-access.log {
            roll_size 10MiB
            roll_keep 10
        }
    }
}
```

Não use `/srv/academia/app` como raiz pública: apenas as duas subpastas indicadas devem ser servidas. Os PDFs desse desenho são acessíveis pelo endereço do arquivo, sem uma nova checagem de login; isso corresponde ao uso direto de `material_pdf.url` no projeto. Não coloque outros documentos ou segredos em `media`.

O Caddy obtém e renova o certificado automaticamente quando o domínio público e a rede estão corretos. Mantenha o serviço e as portas de validação disponíveis. [Fontes: HTTPS automático](https://caddyserver.com/docs/automatic-https) e [handle_path](https://caddyserver.com/docs/caddyfile/directives/handle_path).

```bash
sudo install -d -o caddy -g caddy -m 750 /var/log/caddy
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl enable caddy
sudo systemctl reload caddy
sudo systemctl status caddy --no-pager
```

O `validate` deve informar configuração válida. Ele **não comprova** que o domínio está acessível nem que o certificado foi emitido; isso será testado pelo navegador.

## 10. Firewall e verificação externa

A TI deve ter feito DNS/NAT conforme o guia inicial. Se o servidor novo usar UFW, configure com ela:

```bash
sudo ufw status verbose
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

**Antes de `ufw enable`, confirme a porta e a origem de sua conexão SSH.** Se a TI usa outra porta ou política de firewall, esses comandos precisam ser adaptados para não cortar seu acesso. Não crie liberações de 5432, 8000 ou 2019. Não há necessidade de UFW se a TI usa outro firewall local, desde que aplique as mesmas regras.

De um computador cliente, abra `https://treinamentos.suaempresa.com.br/saude/` usando o domínio real. Espere o JSON de saúde e certificado sem alerta. Repita com um celular com Wi-Fi desligado. Acesso apenas pelo próprio servidor não comprova publicação na internet.

Depois de confirmar HTTPS, altere em `/etc/academia/academia.env`:

```text
SECURE_HSTS_SECONDS='31536000'
```

Mantenha `INCLUDE_SUBDOMAINS` e `PRELOAD` como `False` até a TI decidir aplicar essas políticas adicionais. Reinicie `sudo systemctl restart academia`. O `check --deploy` ainda pode informar os avisos dessas duas opções deliberadamente desativadas; registre essa escolha. Nunca ligue `DEBUG` para resolver um erro em produção.

## 11. Testar o funcionamento completo

1. Entre em `/admin/` com o administrador criado.
2. Cadastre uma empresa de homologação, produto, curso, etapas e questões. Nas questões, marque uma única alternativa correta.
3. Envie um PDF de teste com menos de 20 MB e abra-o pela página do curso. Confira CSS, vídeos locais e vídeos externos que serão usados pela empresa.
4. Cadastre um técnico com um e-mail real de teste e libere o curso.
5. Em uma janela anônima, use **Primeiro acesso**, e-mail e matrícula desse técnico; crie a senha e faça login.
6. Complete as etapas, responda a avaliação e abra o certificado. Confira o código na validação pública.
7. Use **Esqueci minha senha**. Confirme que o e-mail chegou, que o link aponta ao domínio real com HTTPS e que permite trocar a senha.
8. Cadastre um responsável de teste, confira o convite e a ativação de senha.
9. Teste pelo menos uma importação CSV pequena e confira os relatórios. Não use dados reais em testes de exclusão.
10. Registre o resultado e desative os cadastros de homologação quando adequado.

Se o SMTP falhar, confira log, porta 587 liberada, credenciais e remetente autorizado. O teste de recuperação não envia mensagem a contas inexistentes; use o técnico de teste que já concluiu o primeiro acesso e tem senha utilizável.

## 12. Backup integrado diário

Conclua primeiro o script `backup-postgresql-academia` do manual do banco. Este backup integrado interrompe brevemente a aplicação para que PDFs e banco representem o mesmo período. Marque uma janela sem treinamentos, por exemplo 02h00.

```bash
sudo nano /usr/local/sbin/backup-academia
```

Conteúdo:

```bash
#!/bin/bash
set -euo pipefail
umask 077
exec 9>/run/backup-academia.lock
flock -n 9 || exit 1
destino="/var/backups/academia/$(date +%Y%m%d-%H%M%S)"
retomar=0
if systemctl is-active --quiet academia; then
    retomar=1
fi
finalizar() {
    if [ "$retomar" -eq 1 ]; then systemctl start academia; fi
}
trap finalizar EXIT
systemctl stop academia
/usr/local/sbin/backup-postgresql-academia "$destino"
tar -czf "$destino/aplicacao.tar.gz" -C /srv/academia app
tar -czf "$destino/configuracao.tar.gz" /etc/academia /etc/caddy/Caddyfile /etc/systemd/system/academia.service /usr/local/sbin/academia-manage /usr/local/sbin/backup-academia /usr/local/sbin/backup-postgresql-academia
tar -tzf "$destino/aplicacao.tar.gz" > /dev/null
tar -tzf "$destino/configuracao.tar.gz" > /dev/null
echo 'Backup integrado concluido' > "$destino/CONCLUIDO.txt"
echo "$destino"
```

O arquivo `aplicacao.tar.gz` inclui o código e `media`; o ambiente virtual fica fora, pois será recriado. Avisos do tar de remoção de `/` inicial ao arquivar caminhos absolutos são esperados. Não deve haver erros de leitura.

```bash
sudo chmod 700 /usr/local/sbin/backup-academia
sudo /usr/local/sbin/backup-academia
sudo systemctl status academia --no-pager
sudo nano /etc/cron.d/academia-backup
```

No arquivo cron, cole uma linha e termine com Enter:

```text
0 2 * * * root /usr/local/sbin/backup-academia >> /var/log/academia-backup.log 2>&1
```

```bash
sudo chmod 644 /etc/cron.d/academia-backup
sudo systemctl enable --now cron
timedatectl
```

O horário é o do sistema mostrado em `timedatectl`. A TI deve confirmar o fuso do servidor; o Django usa `America/Sao_Paulo` internamente, mas isso não muda o relógio do cron.

Confira diariamente a pasta datada, `CONCLUIDO.txt` e o log. A TI deve configurar cópia criptografada dessa pasta para o destino externo preenchido na ficha e monitorar falhas. O script sozinho não faz cópia externa nem envia alerta. Não configure um backup do banco concorrente. Gerencie a retenção do log e dos arquivos com a TI.

## 13. Recuperação e manutenção

**Para testar:** restaure o banco separado conforme o manual PostgreSQL. Para testar a aplicação completa, use outra VM isolada, restaure `app` e as configurações, recrie o ambiente virtual e aponte ao banco de teste. Nesse ambiente, substitua SMTP por `django.core.mail.backends.console.EmailBackend` e não instale agendamento de lembretes, evitando mensagens a usuários reais.

**Em falha real:** interrompa a entrada de usuários, preserve a instalação atual, restaure em banco novo, extraia os arquivos em uma pasta de recuperação e confira conteúdo antes de substituir a aplicação. Atualize `DATABASE_URL` para o banco restaurado, restaure permissões de `media/staticfiles`, recrie bibliotecas pela lista salva e use o código da mesma cópia do banco. Só reinicie os serviços depois de `check`, conferência das migrações e teste local de saúde. Verifique login, PDF e certificado antes de reabrir o acesso. Não use somente uma versão antiga do código contra um banco já migrado.

**Atualizações:** marque manutenção; gere backup integrado e cópia externa; pare `academia`; guarde a versão anterior; coloque a nova entrega preservando `media` e configurações; instale as dependências da entrega; execute `sudo academia-manage migrate --noinput`, `collectstatic --noinput` e `check --deploy`; inicie o serviço e repita os testes de aceite. Se houver falha após migrações, retorne código e banco compatíveis a partir do backup, com a TI.

**Lembretes de reciclagem, opcionais:** o comando envia e-mails reais e pode repetir avisos a cada execução. Depois da validação do SMTP e aprovação do responsável, crie `/etc/cron.d/academia-lembretes`, modo 644, com `0 8 * * * root /usr/local/sbin/academia-manage enviar_lembretes_reciclagem >> /var/log/academia-lembretes.log 2>&1`. Não habilite em homologação.

## 14. Diagnóstico rápido

```bash
sudo systemctl status academia caddy --no-pager
sudo journalctl -u academia -n 100 --no-pager
sudo journalctl -u caddy -n 100 --no-pager
sudo tail -n 50 /var/log/academia-backup.log
df -h
```

| Sintoma | Verificação |
|---|---|
| 502 Bad Gateway | Serviço academia parado, erro de importação ou porta 8000 errada; confira log e saúde local. |
| 400 Bad Request | Domínio ausente em `DJANGO_ALLOWED_HOSTS`; edite ambiente e reinicie academia. |
| 403 CSRF | Origem HTTPS incorreta, formulário antigo ou proxy não identificando HTTPS; confira domínio e cabeçalho. |
| Redirecionamento infinito | Caddy deve enviar `X-Forwarded-Proto`; confira `USE_X_FORWARDED_PROTO=True`. |
| Sem CSS ou PDF 404 | `collectstatic`, caminhos do Caddy e existência do arquivo; não resolva ligando DEBUG. |
| PDF 403/erro ao enviar | Confira dono/grupo e acesso a `media` para academia/caddy. |
| HTTPS não emite | DNS A/AAAA, NAT, 80/443, saída HTTPS, políticas CAA e relógio; veja log Caddy com a TI. |
| Funciona dentro, não fora | DNS público, CGNAT, firewall e NAT. |
| Funciona fora, não dentro | DNS interno ou retorno NAT; use o mesmo nome do site. |
| E-mail não chega | Teste com usuário ativado; confira SMTP/STARTTLS, remetente e spam. |
| Esqueci a senha administrativa | `sudo academia-manage redefinir_admin --username SEU_ADMIN --email SEU_EMAIL`; o comando solicita senha. |

Não envie logs com senhas ou tokens de recuperação a canais públicos.

## 15. Aceite e reinício

Em janela combinada, reinicie o servidor com `sudo reboot`. Aguarde e reconecte. Sem iniciar programas manualmente, confira site externo, login, PDF e `/saude/`. Confirme `academia`, Caddy, cluster PostgreSQL e cron ativos.

Registre domínio, versão do projeto, versões de bibliotecas, contatos, horário de backup, destino externo e resultado da restauração. Entregue também [Manual do usuário](../uso/MANUAL_USUARIO.md) e [Manual do superadmin](../uso/MANUAL_SUPERADMIN.md).

Este roteiro foi revisado contra o código, sem instalação real em Ubuntu nesta entrega. Todos os testes descritos devem ser realizados pelo instalador antes da liberação.
