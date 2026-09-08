# Manual 2 — Plataforma no Windows Server

Academia Técnica · Edição de 08/09/2026 · Windows Server 2022/2025 com interface gráfica, x64.

**Objetivo:** publicar a aplicação com PostgreSQL local, Waitress, Caddy e HTTPS, mantendo-a funcionando mesmo depois de sair da sessão ou reiniciar. Inclui e-mail, backup e diagnóstico. Reserve meio período de trabalho, além das liberações da rede e testes da empresa.

O Gunicorn do projeto é voltado a Unix. No Windows, este roteiro usa **Waitress**, sem alterar o código Django nem o `requirements.txt` original. O Caddy fornece HTTPS e arquivos; o WinSW permite executar os programas como serviços Windows. [Fonte: Waitress](https://docs.pylonsproject.org/projects/waitress/en/latest/).

## 1. Pré-requisitos

Conclua [PostgreSQL no Windows](01_POSTGRESQL_WINDOWS.md) e a ficha de [Comece aqui](00_LEIA_PRIMEIRO.md). Tenha em mãos:

- Acesso administrativo ao Windows Server e ao IP interno fixo.
- Banco `sistema_treinamentos`, usuário `academia_app` e senha testada.
- Domínio real e DNS/NAT TCP 80/443 configurados pela TI.
- SMTP autenticado com STARTTLS/587, usuário, senha e remetente autorizado.
- Entrega do projeto com `manage.py`, `requirements.txt`, `core` e `treinamentos`.

Os exemplos usam `treinamentos.suaempresa.com.br`; substitua esse nome em todas as configurações e testes. Os caminhos `C:\Academia` e `C:\Python313` devem ser mantidos para que os exemplos se encaixem.

Abra **Windows PowerShell → Executar como administrador**. Execute os blocos `powershell` nessa janela, um de cada vez. Não use Prompt de Comando no lugar do PowerShell. Se um comando falhar, pare naquele passo.

## 2. Instalar o Python

1. Abra a [página oficial de downloads para Windows](https://www.python.org/downloads/windows/).
2. Escolha o instalador Windows **64-bit da série Python 3.13**, na atualização corretiva disponível. Não escolha versão de teste, pacote embeddable nem ARM64.
3. Execute o instalador como administrador. Escolha **Customize installation**.
4. Mantenha `pip`. Nas opções avançadas, escolha instalação **para todos os usuários** e diretório `C:\Python313`.
5. Conclua e abra uma nova janela PowerShell administrativa.

```powershell
& C:\Python313\python.exe --version
& C:\Python313\python.exe -m pip --version
```

Espere `Python 3.13.x` e a identificação do pip. Django 6.0 aceita Python 3.12 a 3.14; não use Python 3.11. [Fonte: Django 6.0](https://docs.djangoproject.com/en/6.0/faq/install/).

Se a TI usar outro método corporativo de distribuição do Python, confirme que o executável é acessível a serviços, não apenas à conta que instalou.

## 3. Criar pastas e colocar o projeto

```powershell
New-Item -ItemType Directory -Force -Path C:\Academia\app,C:\Academia\operacao,C:\Academia\config,C:\Academia\servicos,C:\Academia\logs,C:\Academia\caddy,C:\Academia\caddy-data | Out-Null
icacls C:\Academia /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' '*S-1-5-19:(OI)(CI)RX'
```

Os identificadores representam Administradores, SYSTEM e LocalService, independentemente do idioma do Windows. LocalService será a conta técnica dos dois serviços. Os scripts de backup e suas credenciais continuarão restritos pelas permissões definidas no manual do banco.

Pelo Explorador, copie a entrega para `C:\Academia\app`. `manage.py` precisa ficar **diretamente** nessa pasta. Não copie `venv`, `.venv`, `.git`, `.env`, `__pycache__` ou `db.sqlite3`. Se houver dados reais a preservar, use [Transferir dados existentes](05_TRANSFERIR_DADOS_EXISTENTES.md).

```powershell
Test-Path C:\Academia\app\manage.py
Test-Path C:\Academia\app\requirements.txt
New-Item -ItemType Directory -Force -Path C:\Academia\app\media,C:\Academia\app\staticfiles | Out-Null
icacls C:\Academia\app /grant '*S-1-5-19:(OI)(CI)RX' /T
icacls C:\Academia\app\media /grant '*S-1-5-19:(OI)(CI)M'
icacls C:\Academia\app\staticfiles /grant '*S-1-5-19:(OI)(CI)M'
icacls C:\Academia\logs /grant '*S-1-5-19:(OI)(CI)M'
icacls C:\Academia\caddy-data /grant '*S-1-5-19:(OI)(CI)M'
```

Os dois `Test-Path` devem retornar `True`. O código fica legível pelo serviço; somente mídia, arquivos estáticos, logs e dados do Caddy precisam de escrita.

## 4. Instalar dependências do Windows

Crie um ambiente virtual novo e uma lista auxiliar que exclui apenas o Gunicorn:

```powershell
& C:\Python313\python.exe -m venv C:\Academia\venv
& C:\Academia\venv\Scripts\python.exe -m pip install --upgrade pip
Get-Content C:\Academia\app\requirements.txt | Where-Object { $_ -notmatch '^\s*gunicorn\b' } | Set-Content C:\Academia\operacao\requirements-windows.txt -Encoding UTF8
& C:\Academia\venv\Scripts\python.exe -m pip install -r C:\Academia\operacao\requirements-windows.txt
& C:\Academia\venv\Scripts\python.exe -m pip install 'waitress==3.0.2'
& C:\Academia\venv\Scripts\python.exe -m pip check
& C:\Academia\venv\Scripts\python.exe -m pip freeze | Set-Content C:\Academia\operacao\bibliotecas-instaladas.txt -Encoding UTF8
```

Espere `No broken requirements found`. O `requirements.txt` da aplicação continua intacto. Use a lista instalada para reproduzir o ambiente em recuperação. Não execute `runserver` como serviço de produção.

## 5. Configuração do banco, domínio e e-mail

O projeto não carrega `.env` automaticamente. Neste Windows usaremos um arquivo JSON protegido e um iniciador que o transforma em variáveis de ambiente. Esses arquivos ficam fora da pasta pública.

Gere a chave:

```powershell
& C:\Academia\venv\Scripts\python.exe -c 'import secrets; print(secrets.token_hex(32))'
notepad C:\Academia\config\ambiente.json
```

Copie o conteúdo abaixo, preenchendo `SUBSTITUA` e o domínio. Salve como **Todos os arquivos**, nome `ambiente.json`, codificação UTF-8. Não deixe `.txt` no final. JSON usa aspas duplas, vírgulas entre linhas e nenhuma vírgula depois da última linha.

```json
{
  "DJANGO_DEBUG": "False",
  "DJANGO_SECRET_KEY": "SUBSTITUA_PELA_CHAVE_GERADA",
  "DJANGO_ALLOWED_HOSTS": "treinamentos.suaempresa.com.br,127.0.0.1,localhost",
  "DJANGO_CSRF_TRUSTED_ORIGINS": "https://treinamentos.suaempresa.com.br",
  "DATABASE_URL": "postgresql://academia_app:SUBSTITUA_SENHA_ALFANUMERICA@127.0.0.1:5432/sistema_treinamentos",
  "DB_SSLMODE": "disable",
  "DB_CONN_MAX_AGE": "60",
  "USE_X_FORWARDED_PROTO": "True",
  "SECURE_SSL_REDIRECT": "True",
  "SESSION_COOKIE_SECURE": "True",
  "CSRF_COOKIE_SECURE": "True",
  "SECURE_HSTS_SECONDS": "0",
  "SECURE_HSTS_INCLUDE_SUBDOMAINS": "False",
  "SECURE_HSTS_PRELOAD": "False",
  "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
  "EMAIL_HOST": "SUBSTITUA_SERVIDOR_SMTP",
  "EMAIL_PORT": "587",
  "EMAIL_HOST_USER": "SUBSTITUA_USUARIO_SMTP",
  "EMAIL_HOST_PASSWORD": "SUBSTITUA_SENHA_SMTP",
  "EMAIL_USE_TLS": "True",
  "EMAIL_TIMEOUT": "20",
  "DEFAULT_FROM_EMAIL": "Academia Tecnica <SUBSTITUA_EMAIL_REMETENTE>",
  "PASSWORD_RESET_TIMEOUT": "604800",
  "MAX_CSV_IMPORT_SIZE_BYTES": "2097152"
}
```

Se uma senha SMTP contiver `\` ou `"`, represente como `\\` ou `\"` dentro do JSON. A senha alfanumérica do banco evita caracteres reservados na URL. Se usar símbolos no banco, a senha na URL precisa de percent-encoding; não coloque `@`, `#`, `/` ou `:` crus. `DB_SSLMODE` é separado da URL porque este projeto não utiliza seu parâmetro de consulta `sslmode`.

O SMTP precisa aceitar usuário/senha com STARTTLS. Se o serviço corporativo exigir apenas OAuth ou SMTPS/465, peça um relay compatível à TI; trocar a porta não implementa esses métodos. O backend padrão de console **não envia e-mails**.

Proteja a configuração e confira a sintaxe sem exibir credenciais:

```powershell
icacls C:\Academia\config /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' '*S-1-5-19:(OI)(CI)RX'
& C:\Academia\venv\Scripts\python.exe -c "import json; json.load(open(r'C:\Academia\config\ambiente.json', encoding='utf-8-sig')); print('JSON valido')"
```

Espere `JSON valido`. Isso verifica sintaxe, não a validade das credenciais.

## 6. Criar o iniciador da plataforma

Abra `notepad C:\Academia\operacao\executar.py` e salve o código completo abaixo em UTF-8, sem extensão `.txt`:

```python
import json
import os
from pathlib import Path
import sys

APP = Path(r"C:\Academia\app")
CONFIG = Path(r"C:\Academia\config\ambiente.json")
with CONFIG.open(encoding="utf-8-sig") as arquivo:
    valores = json.load(arquivo)
if not valores.get("DATABASE_URL", "").startswith(("postgres://", "postgresql://")):
    raise SystemExit("Configure DATABASE_URL para PostgreSQL antes de continuar.")
if any("SUBSTITUA" in str(valor) for valor in valores.values()):
    raise SystemExit("Preencha todos os campos SUBSTITUA em ambiente.json.")
for nome, valor in valores.items():
    os.environ[nome] = str(valor)
os.environ["DJANGO_SETTINGS_MODULE"] = "treinamentos.settings"
os.chdir(APP)
sys.path.insert(0, str(APP))
sys.dont_write_bytecode = True

if len(sys.argv) > 1 and sys.argv[1] == "web":
    from waitress import serve
    from treinamentos.wsgi import application
    serve(
        application,
        listen="127.0.0.1:8000",
        threads=4,
        trusted_proxy="127.0.0.1",
        trusted_proxy_headers="x-forwarded-for x-forwarded-proto x-forwarded-host",
    )
else:
    from django.core.management import execute_from_command_line
    execute_from_command_line(["manage.py", *sys.argv[1:]])
```

O iniciador carrega a configuração para a web e para os comandos administrativos. A confiança nos cabeçalhos do proxy fica limitada a `127.0.0.1`, onde estará o Caddy. [Fonte: Waitress atrás de proxy](https://docs.pylonsproject.org/projects/waitress/en/stable/reverse-proxy.html).

## 7. Criar tabelas e administrador

Primeiro comprove o banco:

```powershell
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py shell -c "from django.db import connection; connection.ensure_connection(); print(connection.vendor, connection.settings_dict['NAME'])"
```

Espere exatamente o tipo e nome: `postgresql sistema_treinamentos`. Se falhar, confira o manual PostgreSQL e a configuração. Depois, para instalação vazia:

```powershell
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py migrate --noinput
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py showmigrations
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py collectstatic --noinput
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py createsuperuser
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py check --deploy
```

Confira `[X]` nas migrações. `collectstatic` prepara CSS e vídeos locais. O cadastro de superusuário pede nome, e-mail e senha do administrador **do site**, não do PostgreSQL.

Se for importar dados existentes, faça o apêndice após `migrate` e antes de criar usuários/cadastros novos. Não execute cargas de demonstração. Não rode a suíte de testes usando o banco de produção.

Os avisos de HSTS durante a montagem são esperados porque ele começa desativado. Outros avisos/erros devem ser resolvidos. HSTS será tratado após o teste HTTPS.

## 8. Baixar Caddy e WinSW

1. Baixe o binário padrão **Windows amd64** pelo [site oficial do Caddy](https://caddyserver.com/download), sem plugins adicionais. Salve/renomeie como `C:\Academia\caddy\caddy.exe`.
2. Na [página oficial WinSW 2.12.0](https://github.com/winsw/winsw/releases/tag/v2.12.0), baixe `WinSW-x64.exe`. Estes exemplos de XML usam a série **2.x**; não use uma versão 3 de prévia com eles.
3. Faça duas cópias desse executável em `C:\Academia\servicos`: uma chamada `AcademiaWeb.exe` e outra `AcademiaProxy.exe`.
4. Em Propriedades dos arquivos baixados, use **Desbloquear**, se o Windows mostrar essa opção, após conferir sua origem. Use também a verificação de arquivos prevista pela TI.
5. WinSW 2.x precisa do .NET Framework compatível; Windows Server dessas versões normalmente já o oferece. Se o executável pedir runtime ausente, instale o .NET Framework 4.8 pelo processo oficial da TI antes de continuar.

```powershell
& C:\Academia\caddy\caddy.exe version
Test-Path C:\Academia\servicos\AcademiaWeb.exe
Test-Path C:\Academia\servicos\AcademiaProxy.exe
```

Espere a versão do Caddy e dois `True`. [Fontes: Caddy como serviço](https://caddyserver.com/docs/running) e [configuração WinSW 2.x](https://github.com/winsw/winsw/blob/v2.12.0/doc/xmlConfigFile.md).

## 9. Criar o serviço da aplicação

Abra `notepad C:\Academia\servicos\AcademiaWeb.xml`. Cole e salve:

```xml
<service>
  <id>AcademiaWeb</id>
  <name>Academia Tecnica - Aplicacao</name>
  <description>Django atendido por Waitress em 127.0.0.1:8000</description>
  <executable>C:\Academia\venv\Scripts\python.exe</executable>
  <arguments>-u C:\Academia\operacao\executar.py web</arguments>
  <workingdirectory>C:\Academia\app</workingdirectory>
  <startmode>Automatic</startmode>
  <depend>postgresql-x64-18</depend>
  <serviceaccount>
    <domain>NT AUTHORITY</domain>
    <user>LocalService</user>
  </serviceaccount>
  <logpath>C:\Academia\logs</logpath>
  <log mode="roll" />
  <onfailure action="restart" delay="10 sec" />
  <stoptimeout>30 sec</stoptimeout>
</service>
```

Se o serviço PostgreSQL tem nome diferente, troque o valor de `<depend>` pelo nome conferido no manual do banco. Arquivos `.exe` e `.xml` precisam ter exatamente o mesmo nome-base.

```powershell
& C:\Academia\servicos\AcademiaWeb.exe install
Start-Service AcademiaWeb
Get-Service AcademiaWeb
curl.exe -i -H 'X-Forwarded-Proto: https' http://127.0.0.1:8000/saude/
```

Espere `Running` e HTTP 200 com `{"status": "ok", "database": "ok"}`. Se falhar, examine os arquivos de log em `C:\Academia\logs` antes de continuar. A porta 8000 deve permanecer restrita ao servidor.

## 10. Configurar Caddy e HTTPS

Abra `notepad C:\Academia\caddy\Caddyfile`. Salve como **Todos os arquivos**, nome `Caddyfile` sem `.txt`. Cole, trocando domínio e e-mail:

```caddyfile
{
    email SUBSTITUA_EMAIL_DA_TI
    storage file_system {
        root C:/Academia/caddy-data
    }
}

treinamentos.suaempresa.com.br {
    encode zstd gzip
    header X-Content-Type-Options nosniff
    handle_path /static/* {
        root * C:/Academia/app/staticfiles
        file_server
    }
    handle_path /media/* {
        root * C:/Academia/app/media
        file_server
    }
    handle {
        reverse_proxy 127.0.0.1:8000 {
            header_up X-Forwarded-Proto {scheme}
        }
    }
    log {
        output file C:/Academia/logs/caddy-access.log {
            roll_size 10MiB
            roll_keep 10
        }
    }
}
```

As barras `/` nesses caminhos do Caddy são intencionais. A raiz pública nunca deve ser `C:/Academia/app` inteira. Os PDFs serão servidos diretamente por URL, conforme os links de `material_pdf.url` usados no projeto; não há nova autenticação no arquivo. Não guarde documentos alheios aos cursos nem segredos em `media`.

Valide a sintaxe:

```powershell
& C:\Academia\caddy\caddy.exe validate --config C:\Academia\caddy\Caddyfile --adapter caddyfile
```

Depois crie `C:\Academia\servicos\AcademiaProxy.xml`:

```xml
<service>
  <id>AcademiaProxy</id>
  <name>Academia Tecnica - HTTPS</name>
  <description>Caddy - HTTPS e arquivos da Academia</description>
  <executable>C:\Academia\caddy\caddy.exe</executable>
  <arguments>run --config C:\Academia\caddy\Caddyfile --adapter caddyfile</arguments>
  <workingdirectory>C:\Academia\caddy</workingdirectory>
  <startmode>Automatic</startmode>
  <serviceaccount>
    <domain>NT AUTHORITY</domain>
    <user>LocalService</user>
  </serviceaccount>
  <logpath>C:\Academia\logs</logpath>
  <log mode="roll" />
  <onfailure action="restart" delay="10 sec" />
  <stoptimeout>30 sec</stoptimeout>
</service>
```

```powershell
& C:\Academia\servicos\AcademiaProxy.exe install
New-NetFirewallRule -DisplayName 'Academia HTTP' -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
New-NetFirewallRule -DisplayName 'Academia HTTPS' -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
Start-Service AcademiaProxy
Get-Service AcademiaWeb,AcademiaProxy
```

As regras acima são para o Windows local; não substituem DNS e NAT no firewall da empresa. Se houver política centralizada, a TI deve aplicá-las por essa política. Se IIS ou outro programa já usa essas portas, não o encerre: adapte a publicação com a TI.

O Caddy emite e renova certificados para o domínio configurado. Isso depende de DNS, acesso público, saída para a autoridade certificadora e relógio correto. [Fonte: HTTPS automático](https://caddyserver.com/docs/automatic-https).

## 11. Validar HTTPS dentro e fora da empresa

1. Abra `https://treinamentos.suaempresa.com.br/saude/`, usando o domínio real, em outra máquina.
2. Espere o JSON de saúde e certificado sem aviso no navegador.
3. Faça o mesmo em um celular com Wi-Fi desligado.
4. Abra a página inicial e confira o visual. CSS ausente normalmente significa problema em `staticfiles` ou no Caddy.

Depois de comprovar o HTTPS, em `ambiente.json` altere `SECURE_HSTS_SECONDS` para `31536000` e execute `Restart-Service AcademiaWeb`. Mantenha `INCLUDE_SUBDOMAINS` e `PRELOAD` como `False` até a TI decidir sobre essas políticas extras. O `check --deploy` pode continuar avisando sobre essas duas opções; registre a escolha.

Não ligue `DEBUG=True` para resolver problemas de publicação. Se ficar redirecionando sem parar, confira os cabeçalhos do proxy e a lista confiável do Waitress.

## 12. Teste de aceite funcional

1. Acesse `/admin/` e entre com o administrador do site.
2. Cadastre empresa, produto e curso de homologação; inclua etapa de conteúdo e avaliação com alternativa correta.
3. Envie um PDF de teste menor que 20 MB. Abra o arquivo e teste os vídeos que serão utilizados pela empresa.
4. Cadastre técnico com e-mail real de teste, matrícula e liberação do curso.
5. Em janela anônima, faça **Primeiro acesso** como esse técnico, defina senha e entre.
6. Conclua as etapas e a avaliação. Confira certificado, impressão e validação pública pelo código.
7. Use **Esqueci minha senha** com a conta ativada. Confirme recebimento, domínio HTTPS do link e troca de senha.
8. Cadastre responsável de teste e confirme convite e definição de senha.
9. Faça importação CSV pequena e confira o relatório.
10. Registre resultados e desative cadastros de homologação ao terminar, conforme decisão do responsável.

A recuperação não envia mensagem a e-mails inexistentes nem a usuários sem senha utilizável. Teste com a conta do técnico que concluiu o primeiro acesso. SMTP, spam e autorização do remetente precisam ser conferidos se o e-mail não chegar.

## 13. Backup completo e automático

O manual PostgreSQL já criou `C:\Academia\backup\Backup-Banco.ps1`. O script a seguir usa esse backup e copia código, PDFs e configuração. Ele pausa brevemente a aplicação para manter arquivos e banco coerentes. Use uma janela combinada com a empresa.

Abra `notepad C:\Academia\backup\Backup-Completo.ps1` e cole:

```powershell
$ErrorActionPreference = 'Stop'
$Destino = Join-Path 'C:\Academia\backups' (Get-Date -Format 'yyyyMMdd-HHmmss')
$Retomar = (Get-Service AcademiaWeb).Status -eq 'Running'
try {
    Stop-Service AcademiaWeb
    New-Item -ItemType Directory -Path $Destino | Out-Null
    & C:\Academia\backup\Backup-Banco.ps1 -Destino $Destino
    foreach ($Nome in @('app','config','operacao','servicos','caddy','backup')) {
        & robocopy.exe "C:\Academia\$Nome" "$Destino\$Nome" /E /COPY:DAT /DCOPY:DAT /R:2 /W:2 /NFL /NDL /NP
        if ($LASTEXITCODE -ge 8) { throw "Falha ao copiar $Nome" }
    }
    'Backup completo concluido' | Set-Content (Join-Path $Destino 'CONCLUIDO.txt')
    Write-Output "Backup concluido em $Destino"
}
finally {
    if ($Retomar) { Start-Service AcademiaWeb }
}
```

`robocopy` usa códigos 0 a 7 para resultados sem falha de cópia; por isso a checagem é `>= 8`. O script não copia `venv` (recriado pelas bibliotecas salvas), logs ou o armazenamento ativo de certificados do Caddy (que podem ser reemitidos). As configurações e senhas estão incluídas: mantenha o backup restrito e criptografado no destino externo.

Execute uma vez:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File C:\Academia\backup\Backup-Completo.ps1
Get-Service AcademiaWeb
```

Espere mensagem de conclusão, arquivo `CONCLUIDO.txt` e serviço de volta a `Running`. Se a política corporativa bloquear o script, peça assinatura/aprovação à TI, sem desativar a política global.

Para agendar:

1. Abra **Agendador de Tarefas** no menu Iniciar.
2. Clique em **Criar Tarefa**, não “Criar Tarefa Básica”.
3. Nome: `Academia - Backup completo`.
4. Em **Alterar Usuário ou Grupo**, escolha `SYSTEM`; marque **Executar com privilégios mais altos**. Essa conta tem acesso às pastas de backup protegidas.
5. Em **Disparadores**, crie execução diária às **02:00**, ou outro horário aprovado.
6. Em **Ações**, escolha iniciar programa: `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`.
7. Argumentos: `-NoProfile -ExecutionPolicy RemoteSigned -File C:\Academia\backup\Backup-Completo.ps1`.
8. Iniciar em: `C:\Academia\backup`.
9. Em **Configurações**, se já estiver em execução, escolha **Não iniciar nova instância**. Permita executar manualmente e executar assim que possível se perder o horário.
10. Salve; clique com botão direito na tarefa → **Executar**. Confira **Último Resultado: 0x0**, pasta nova e `CONCLUIDO.txt`.

O horário é o do Windows, não necessariamente o do Django. Confira Data e Hora do servidor. Não agende outro backup do banco ao mesmo tempo. Diariamente, a TI deve copiar a pasta completa para o cofre externo, verificar falhas e espaço livre. Este script não copia para outro equipamento nem envia alertas sozinho.

## 14. Restauração, atualização e lembretes

**Restauração de teste:** execute o banco separado do manual PostgreSQL. Para testar também a plataforma, use outra VM isolada, copie `app`, `config`, `operacao` e serviços do backup, recrie o ambiente virtual pelas bibliotecas salvas e aponte para o banco restaurado. Troque o backend de e-mail para `django.core.mail.backends.console.EmailBackend`; não agende lembretes nesse ambiente.

**Recuperação real:** pare `AcademiaWeb`, preserve a instalação danificada, restaure o banco em um novo nome, recupere o código e a pasta `media` do mesmo backup e atualize `DATABASE_URL`. Reaplique as permissões das seções 3 e 5, confira as migrações e teste saúde, login, PDF e certificado antes de liberar usuários. A senha de `academia_app` no novo servidor precisa corresponder à configuração e ao `pgpass.conf`. Não restaure código antigo sobre banco mais novo sem plano de reversão.

**Atualização do projeto:** marque manutenção; gere backup e confirme a cópia externa; pare `AcademiaWeb`; guarde a entrega anterior; coloque a nova versão preservando `media` e configuração; regenere a lista auxiliar de dependências Windows e instale-a; execute migrações, `collectstatic` e `check --deploy` pelo `executar.py`; inicie o serviço e repita o aceite. Se alterar XML de serviço, use o comando `refresh` do respectivo WinSW antes de reiniciar; mudanças somente no JSON são aplicadas ao reiniciar `AcademiaWeb`. Para Caddyfile, valide e reinicie `AcademiaProxy`.

**Lembretes opcionais:** após SMTP validado e liberação do responsável, crie outra tarefa agendada usando `C:\Academia\venv\Scripts\python.exe`, argumentos `C:\Academia\operacao\executar.py enviar_lembretes_reciclagem`, iniciar em `C:\Academia\app`, diariamente às 08h00. O comando envia e-mails reais e pode reenviar avisos a cada execução. Não habilite em homologação. Monitore o resultado da tarefa.

## 15. Diagnóstico

```powershell
Get-Service AcademiaWeb,AcademiaProxy,postgresql-x64-18
Get-ChildItem C:\Academia\logs
Get-PSDrive C
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 80,443,5432,8000,2019 }
```

Abra o log mais recente correspondente ao serviço com Bloco de Notas. Consulte também **Visualizador de Eventos → Logs do Windows → Aplicativo/Sistema**.

| Sintoma | Conferir |
|---|---|
| Serviço instala mas não inicia | Nome do XML/EXE, caminho Python, dependência PostgreSQL e logs WinSW. |
| Funciona como administrador, falha como serviço | Permissões LocalService no código, configuração, Python, logs e mídia. |
| JSONDecodeError | Vírgulas/aspas e codificação de `ambiente.json`; rode o teste de sintaxe da seção 5. |
| 502 Bad Gateway | AcademiaWeb ativo, saúde local e porta 8000. |
| 400 Bad Request | Nome real em `DJANGO_ALLOWED_HOSTS`, sem protocolo. |
| 403 CSRF | Origem HTTPS exata e configuração do proxy/Waitress. |
| Redirecionamento infinito | `X-Forwarded-Proto` e cabeçalhos confiáveis do Waitress. |
| CSS/PDF ausente | `collectstatic`, arquivos e permissões; mapeamentos `/static/*` e `/media/*`. |
| HTTPS não emite | DNS/AAAA, NAT, 80/443, CAA, relógio e saída HTTPS; veja log Caddy. |
| Só funciona na rede interna | DNS público, firewall, NAT ou CGNAT. |
| Só funciona fora da empresa | DNS interno ou retorno NAT. |
| SMTP falha | STARTTLS/587, credenciais, remetente e restrições de saída. |
| Tarefa de backup falha | Conta SYSTEM, caminhos, política de scripts, espaço e `pgpass.conf`. |

Para recuperar acesso administrativo, o comando abaixo pede a nova senha:

```powershell
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py redefinir_admin --username SEU_ADMIN --email SEU_EMAIL
```

Não compartilhe o JSON, senhas ou tokens de recuperação ao enviar logs para suporte.

## 16. Entrega final

Reinicie o servidor em janela combinada usando o menu do Windows. Depois, **sem abrir manualmente os programas**, teste novamente HTTPS externo, login, PDF e saúde; confira os três serviços. Registre a versão do projeto, inventário de bibliotecas, domínio, instalador, contatos, agendamento, destino externo e resultado de restauração.

Entregue [Manual do usuário](../uso/MANUAL_USUARIO.md) e [Manual do superadmin](../uso/MANUAL_SUPERADMIN.md) aos responsáveis. O roteiro foi conferido contra o código e as fontes citadas, mas não executado em servidor Windows de produção nesta entrega. O aceite no ambiente real é indispensável.
