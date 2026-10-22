# Manual 1 — Instalar no Windows Server

Academia Técnica · Edição de 22/10/2026 · Windows Server 2022/2025, 64 bits, com interface gráfica.

Leia antes o [Comece aqui](00_LEIA_PRIMEIRO.md) e tenha a ficha preenchida. Tempo estimado: 2 a 3 horas, sem contar as liberações de rede da TI.

**Como executar os comandos:** abra o menu Iniciar, procure **Windows PowerShell**, clique com o botão direito e escolha **Executar como administrador**. Use essa janela para todos os blocos. Não use o Prompt de Comando.

## Visão geral das pastas

Ao final, o servidor terá esta estrutura:

```text
C:\Academia\
├── app\          código da plataforma (substituído a cada atualização)
├── venv\         bibliotecas Python da plataforma
├── config\       ambiente.json — configurações e senhas (protegido)
├── operacao\     executar.py e backup.py
├── dados\        academia.sqlite3 (banco) e media\ (PDFs dos cursos)
├── backups\      cópias diárias do banco e dos PDFs
├── servicos\     programas que mantêm o site ligado (WinSW)
├── caddy\        Caddy (HTTPS) e Caddyfile
├── caddy-data\   certificados HTTPS
└── logs\         registros dos serviços
```

O que é mais importante proteger e copiar no backup: **`dados`** e **`config`**.

## Passo 1 — Instalar o Python 3.13

1. Abra [python.org/downloads/windows](https://www.python.org/downloads/windows/).
2. Baixe o **Windows installer (64-bit)** da versão **Python 3.13** mais recente. Não use versões "pre-release", "embeddable" nem ARM64.
3. Execute o instalador e clique em **Customize installation**.
4. Na primeira tela, deixe `pip` marcado e clique em **Next**.
5. Na tela seguinte, marque **Install Python 3.13 for all users** e troque o local para `C:\Python313`. Clique em **Install**.
6. Feche e abra de novo o PowerShell como administrador.

```powershell
& C:\Python313\python.exe --version
```

**Resultado esperado:** `Python 3.13.x`.

## Passo 2 — Criar as pastas e definir permissões

```powershell
New-Item -ItemType Directory -Force -Path C:\Academia\app,C:\Academia\config,C:\Academia\operacao,C:\Academia\dados\media,C:\Academia\backups,C:\Academia\servicos,C:\Academia\caddy,C:\Academia\caddy-data,C:\Academia\logs | Out-Null

# Somente Administradores e SYSTEM têm controle total; o serviço (LocalService) só lê
icacls C:\Academia /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F' '*S-1-5-19:(OI)(CI)RX'

# O serviço precisa gravar no banco, nos PDFs, nos logs e nos certificados
icacls C:\Academia\dados /grant '*S-1-5-19:(OI)(CI)M'
icacls C:\Academia\logs /grant '*S-1-5-19:(OI)(CI)M'
icacls C:\Academia\caddy-data /grant '*S-1-5-19:(OI)(CI)M'

# Backups: só Administradores e SYSTEM
icacls C:\Academia\backups /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F'
```

**Resultado esperado:** cada `icacls` termina com `Successfully processed 1 files` (ou `Êxito ao processar 1 arquivos`).

Os códigos `S-1-5-...` representam Administradores, SYSTEM e LocalService e funcionam em Windows de qualquer idioma. LocalService é a conta que vai executar o site.

## Passo 3 — Copiar o código da plataforma

Copie a pasta do projeto para `C:\Academia\app` pelo Explorador. O arquivo `manage.py` precisa ficar **diretamente** em `C:\Academia\app`.

**Não copie** estas pastas e arquivos, se existirem: `venv`, `.venv`, `.git`, `__pycache__`, `db.sqlite3`, `media`, `staticfiles`, `dist`. Os dados atuais, se houver, são levados pelo [Manual 2](02_TRANSFERIR_DADOS.md), no momento indicado no Passo 7.

```powershell
Test-Path C:\Academia\app\manage.py
Test-Path C:\Academia\app\requirements.txt
```

**Resultado esperado:** `True` duas vezes.

## Passo 4 — Instalar as bibliotecas

```powershell
& C:\Python313\python.exe -m venv C:\Academia\venv
& C:\Academia\venv\Scripts\python.exe -m pip install --upgrade pip
& C:\Academia\venv\Scripts\python.exe -m pip install -r C:\Academia\app\requirements.txt waitress==3.0.2
& C:\Academia\venv\Scripts\python.exe -m pip check
```

**Resultado esperado:** a última linha é `No broken requirements found.`

O `requirements.txt` também instala o Gunicorn, que só funciona em Linux. Ele fica instalado sem uso; no Windows quem executa o site é o **Waitress**.

## Passo 5 — Criar a configuração

Primeiro gere uma chave secreta e copie o resultado (uma linha longa de letras e números):

```powershell
& C:\Academia\venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Abra o Bloco de Notas no arquivo de configuração:

```powershell
notepad C:\Academia\config\ambiente.json
```

O Bloco de Notas pergunta se quer criar o arquivo: responda **Sim**. Cole o conteúdo abaixo e troque cada `SUBSTITUA_...`:

```json
{
  "DJANGO_DEBUG": "False",
  "DJANGO_SECRET_KEY": "SUBSTITUA_PELA_CHAVE_GERADA",
  "DJANGO_ALLOWED_HOSTS": "SUBSTITUA_ENDERECO_DO_SITE,127.0.0.1,localhost",
  "DJANGO_CSRF_TRUSTED_ORIGINS": "https://SUBSTITUA_ENDERECO_DO_SITE",

  "SQLITE_PATH": "C:/Academia/dados/academia.sqlite3",
  "DJANGO_MEDIA_ROOT": "C:/Academia/dados/media",

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
  "DEFAULT_FROM_EMAIL": "Academia Tecnica <SUBSTITUA_EMAIL_REMETENTE>"
}
```

Cuidados:

- `SUBSTITUA_ENDERECO_DO_SITE` é só o nome, sem `https://` e sem barra no final. Exemplo: `treinamentos.suaempresa.com.br`. Na linha `DJANGO_CSRF_TRUSTED_ORIGINS` o `https://` já está escrito.
- Use barras normais `/` nos caminhos, como no modelo.
- Se a senha do SMTP tiver `"` ou `\`, escreva `\"` ou `\\` no lugar.
- O SMTP precisa aceitar usuário e senha com STARTTLS na porta 587. Se a empresa só permitir OAuth ou a porta 465, peça à TI um relay compatível.

Salve com **Arquivo → Salvar como**, tipo **Todos os arquivos**, nome `ambiente.json`, codificação **UTF-8**. Confira que o nome não ficou `ambiente.json.txt`.

Teste se o arquivo está correto (o comando não mostra as senhas):

```powershell
& C:\Academia\venv\Scripts\python.exe -c "import json; d=json.load(open(r'C:\Academia\config\ambiente.json', encoding='utf-8-sig')); print('JSON valido'); print('Falta preencher:', [k for k,v in d.items() if 'SUBSTITUA' in v] or 'nada')"
```

**Resultado esperado:** `JSON valido` e `Falta preencher: nada`.

## Passo 6 — Criar o iniciador

O projeto não lê o `ambiente.json` sozinho. Este pequeno programa carrega a configuração e depois executa o site ou um comando administrativo.

```powershell
notepad C:\Academia\operacao\executar.py
```

Responda **Sim** para criar, cole o código abaixo e salve (tipo **Todos os arquivos**, codificação UTF-8):

```python
import json
import os
import sys
from pathlib import Path

APP = Path(r"C:\Academia\app")
CONFIG = Path(r"C:\Academia\config\ambiente.json")

with CONFIG.open(encoding="utf-8-sig") as arquivo:
    valores = json.load(arquivo)
if not valores.get("SQLITE_PATH"):
    raise SystemExit("Configure SQLITE_PATH em ambiente.json.")
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

A partir daqui, todo comando administrativo da plataforma é executado assim:

```text
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py NOME_DO_COMANDO
```

Confira se a configuração aponta para o banco certo:

```powershell
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['NAME']); print('DEBUG =', settings.DEBUG)"
```

**Resultado esperado:** `C:\Academia\dados\academia.sqlite3` (ou com barras `/`) e `DEBUG = False`.

## Passo 7 — Preparar o banco de dados

Escolha **um** dos caminhos:

### Caminho A — Começar com o banco vazio

```powershell
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py migrate --noinput
```

**Resultado esperado:** várias linhas `Applying ... OK`, terminando sem erro. O arquivo `C:\Academia\dados\academia.sqlite3` passa a existir.

### Caminho B — Trazer os dados atuais

Siga agora o [Manual 2 — Trazer os dados atuais](02_TRANSFERIR_DADOS.md) e volte para o Passo 8 ao terminar.

## Passo 8 — Criar ou redefinir o administrador

Este comando cria o administrador do site, ou troca a senha dele se já existir (por exemplo, quando os dados foram trazidos e ninguém lembra a senha):

```powershell
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py redefinir_admin --username admin --email SUBSTITUA_EMAIL_DO_ADMIN
```

O comando pede a senha duas vezes; ela não aparece enquanto você digita. Use pelo menos 8 caracteres e não use só números nem senhas comuns.

**Resultado esperado:** `Administrador 'admin' criado com sucesso.` (ou `redefinido`). Se a senha for recusada, o comando explica o motivo e **nada é alterado**; basta rodar de novo.

## Passo 9 — Preparar os arquivos visuais e conferir

```powershell
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py collectstatic --noinput
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py check --deploy
```

**Resultado esperado:** o primeiro mostra `... static files copied to 'C:\Academia\app\staticfiles'`. O segundo pode mostrar avisos sobre **HSTS** (`security.W004`, `W005`, `W021`); eles são esperados neste momento e serão tratados no Passo 13. Qualquer outro aviso deve ser resolvido antes de seguir.

## Passo 10 — Baixar o Caddy e o WinSW

1. Baixe o Caddy em [caddyserver.com/download](https://caddyserver.com/download): plataforma **Windows amd64**, sem plugins. Salve como `C:\Academia\caddy\caddy.exe`.
2. Baixe o WinSW 2.12.0 em [github.com/winsw/winsw/releases/tag/v2.12.0](https://github.com/winsw/winsw/releases/tag/v2.12.0): arquivo `WinSW-x64.exe`. Use a versão 2.x; os modelos abaixo não servem para a versão 3.
3. Em `C:\Academia\servicos`, faça **duas cópias** do `WinSW-x64.exe`: uma chamada `AcademiaWeb.exe` e outra `AcademiaProxy.exe`.
4. Se o Windows mostrar a opção **Desbloquear** nas Propriedades dos arquivos baixados, marque-a.

```powershell
& C:\Academia\caddy\caddy.exe version
Test-Path C:\Academia\servicos\AcademiaWeb.exe, C:\Academia\servicos\AcademiaProxy.exe
```

**Resultado esperado:** a versão do Caddy e `True` duas vezes.

## Passo 11 — Criar o serviço da plataforma

Um **serviço** é um programa que o Windows mantém ligado, mesmo sem ninguém conectado, e que volta sozinho depois de reiniciar o servidor.

```powershell
notepad C:\Academia\servicos\AcademiaWeb.xml
```

Cole e salve (tipo **Todos os arquivos**):

```xml
<service>
  <id>AcademiaWeb</id>
  <name>Academia Tecnica - Aplicacao</name>
  <description>Plataforma Academia Tecnica (Waitress em 127.0.0.1:8000)</description>
  <executable>C:\Academia\venv\Scripts\python.exe</executable>
  <arguments>-u C:\Academia\operacao\executar.py web</arguments>
  <workingdirectory>C:\Academia\app</workingdirectory>
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

Instale, inicie e teste:

```powershell
& C:\Academia\servicos\AcademiaWeb.exe install
Start-Service AcademiaWeb
Get-Service AcademiaWeb
curl.exe -s -H "X-Forwarded-Proto: https" http://127.0.0.1:8000/saude/
```

**Resultado esperado:** `Running` e `{"status": "ok", "database": "ok"}`.

Se não funcionar, abra o arquivo mais recente em `C:\Academia\logs` que começa com `AcademiaWeb` para ver o erro.

## Passo 12 — Configurar o HTTPS com o Caddy

```powershell
notepad C:\Academia\caddy\Caddyfile
```

Salve como **Todos os arquivos**, nome `Caddyfile` (sem extensão). Cole, trocando o e-mail e o endereço do site:

```caddyfile
{
    email SUBSTITUA_EMAIL_DA_TI
    storage file_system {
        root C:/Academia/caddy-data
    }
}

SUBSTITUA_ENDERECO_DO_SITE {
    encode zstd gzip
    header X-Content-Type-Options nosniff

    handle_path /static/* {
        root * C:/Academia/app/staticfiles
        file_server
    }

    handle {
        reverse_proxy 127.0.0.1:8000 {
            header_up X-Forwarded-Proto {scheme}
        }
    }

    log {
        output file C:/Academia/logs/caddy-acessos.log {
            roll_size 10MiB
            roll_keep 10
        }
    }
}
```

Não há regra para `/media/`: os PDFs dos cursos são entregues pela própria plataforma, **somente para quem está logado e tem acesso ao curso**. Não aponte o Caddy para `C:\Academia\dados`.

Valide o arquivo:

```powershell
& C:\Academia\caddy\caddy.exe validate --config C:\Academia\caddy\Caddyfile --adapter caddyfile
```

**Resultado esperado:** `Valid configuration`.

Agora crie o serviço do Caddy:

```powershell
notepad C:\Academia\servicos\AcademiaProxy.xml
```

```xml
<service>
  <id>AcademiaProxy</id>
  <name>Academia Tecnica - HTTPS</name>
  <description>Caddy: HTTPS da Academia Tecnica</description>
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

Instale, libere as portas no firewall do Windows e inicie:

```powershell
& C:\Academia\servicos\AcademiaProxy.exe install
New-NetFirewallRule -DisplayName 'Academia HTTP' -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow
New-NetFirewallRule -DisplayName 'Academia HTTPS' -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
Start-Service AcademiaProxy
Get-Service AcademiaWeb, AcademiaProxy
```

**Resultado esperado:** os dois serviços em `Running`.

O Caddy obtém o certificado HTTPS sozinho, desde que o DNS e o encaminhamento das portas 80/443 estejam prontos.

## Passo 13 — Testar o acesso

1. Em outro computador, abra `https://SEU_ENDERECO/saude/`. Deve aparecer `{"status": "ok", "database": "ok"}` e o navegador não deve dar aviso de certificado.
2. Repita num celular com o Wi-Fi desligado (acesso de fora da empresa).
3. Abra a página inicial e confira se o visual (cores, logo) aparece.

Com o HTTPS funcionando, ative o HSTS: no `ambiente.json`, troque `"SECURE_HSTS_SECONDS": "0"` por `"SECURE_HSTS_SECONDS": "31536000"` e reinicie:

```powershell
Restart-Service AcademiaWeb
```

**Nunca** ligue `DJANGO_DEBUG` em produção para investigar um problema; use os logs.

## Passo 14 — Teste completo de funcionamento

1. Entre em `https://SEU_ENDERECO/admin/` com o administrador do Passo 8.
2. Cadastre uma empresa, um produto e um curso de teste com um PDF, uma etapa de conteúdo e uma prova.
3. Cadastre um técnico de teste com um e-mail real e libere o curso para ele.
4. Numa janela anônima, faça o **Primeiro acesso** como esse técnico. Ele deve receber um e-mail com link `https://`; use o link para criar a senha e entre.
5. Abra o PDF do curso. Copie o endereço do PDF, abra outra janela anônima (sem login) e cole: deve ir para a tela de login.
6. Conclua o curso e a prova. Confira o certificado e a validação pública pelo código.
7. Saia e use **Esqueci minha senha** com o técnico. O e-mail deve chegar com link `https://`.
8. Cadastre um responsável de teste e confira se o convite por e-mail chega.
9. Ao final, desative os cadastros de teste.

## Passo 15 — Backup automático

O backup copia o banco com segurança **sem desligar o site**, junto com os PDFs e a configuração, e mantém as últimas 14 cópias.

```powershell
notepad C:\Academia\operacao\backup.py
```

Cole e salve (tipo **Todos os arquivos**, UTF-8):

```python
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DADOS = Path(r"C:\Academia\dados")
CONFIG = Path(r"C:\Academia\config\ambiente.json")
BACKUPS = Path(r"C:\Academia\backups")
MANTER = 14

destino = BACKUPS / datetime.now().strftime("%Y%m%d-%H%M%S")
destino.mkdir(parents=True)

# Copia consistente do banco, mesmo com o site em uso
origem = sqlite3.connect(DADOS / "academia.sqlite3")
copia = sqlite3.connect(destino / "academia.sqlite3")
origem.backup(copia)
resultado = copia.execute("PRAGMA integrity_check").fetchone()[0]
copia.close()
origem.close()
if resultado != "ok":
    sys.exit(f"Copia do banco com problema: {resultado}")

if (DADOS / "media").exists():
    shutil.copytree(DADOS / "media", destino / "media")
shutil.copy2(CONFIG, destino / "ambiente.json")
(destino / "CONCLUIDO.txt").write_text("Backup concluido\n", encoding="utf-8")

antigos = sorted(p for p in BACKUPS.iterdir() if (p / "CONCLUIDO.txt").exists())
for pasta in antigos[:-MANTER]:
    shutil.rmtree(pasta)

print(f"Backup concluido em {destino}")
```

Teste:

```powershell
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\backup.py
```

**Resultado esperado:** `Backup concluido em C:\Academia\backups\AAAAMMDD-HHMMSS`, e a pasta contém `academia.sqlite3`, `media`, `ambiente.json` e `CONCLUIDO.txt`.

Agende para rodar todo dia:

1. Abra o **Agendador de Tarefas** e clique em **Criar Tarefa** (não "Criar Tarefa Básica").
2. **Geral:** nome `Academia - Backup`. Em **Alterar Usuário ou Grupo**, digite `SYSTEM`. Marque **Executar com privilégios mais altos**.
3. **Disparadores → Novo:** diariamente, às 02:00 (ou outro horário combinado).
4. **Ações → Novo:** Programa `C:\Academia\venv\Scripts\python.exe`; Argumentos `C:\Academia\operacao\backup.py`; Iniciar em `C:\Academia\operacao`.
5. **Configurações:** marque **Executar a tarefa assim que possível após uma inicialização agendada ter sido perdida**. Em "Se a tarefa já estiver em execução", escolha **Não iniciar uma nova instância**.
6. Salve, clique com o botão direito na tarefa e escolha **Executar**. Confira **Resultado da última execução: (0x0)** e uma pasta nova em `C:\Academia\backups`.

**Importante:** o backup dentro do próprio servidor não protege contra perda do servidor. A TI deve copiar diariamente a pasta `C:\Academia\backups` para o destino externo da ficha. A pasta contém dados pessoais e senhas: mantenha o destino protegido.

> **Nunca copie o arquivo `academia.sqlite3` com o Explorador enquanto o site está ligado.** A cópia pode sair corrompida. Use sempre o `backup.py` ou pare o serviço `AcademiaWeb` antes.

## Passo 16 — Lembretes de reciclagem por e-mail (opcional)

A plataforma pode avisar os técnicos sobre certificados vencidos ou perto de vencer. Só ative depois de validar o e-mail no Passo 14 e com o aval do responsável.

Crie outra tarefa no Agendador, como no Passo 15, com:

- Nome `Academia - Lembretes`, usuário `SYSTEM`, diariamente às 08:00.
- Programa `C:\Academia\venv\Scripts\python.exe`; Argumentos `C:\Academia\operacao\executar.py enviar_lembretes_reciclagem`; Iniciar em `C:\Academia\app`.

O comando envia e-mails reais a cada execução.

## Passo 17 — Reiniciar e entregar

Reinicie o servidor numa janela combinada. Sem abrir nada manualmente, confira:

```powershell
Get-Service AcademiaWeb, AcademiaProxy
```

Os dois devem estar `Running`, e o site deve abrir de fora da empresa. Refaça o login e abra um PDF.

Registre: data, versão do projeto entregue, endereço do site, local dos backups externos, quem instalou e o contato de suporte.

## Atualizar a plataforma no futuro

1. Rode o backup: `& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\backup.py`.
2. Pare o site: `Stop-Service AcademiaWeb`.
3. Renomeie `C:\Academia\app` para `C:\Academia\app-anterior` e copie a nova versão para `C:\Academia\app` (mesmas exclusões do Passo 3). Os dados ficam em `C:\Academia\dados` e não são afetados.
4. Reaplique a permissão de leitura: `icacls C:\Academia\app /grant '*S-1-5-19:(OI)(CI)RX' /T`.
5. Rode:

```powershell
& C:\Academia\venv\Scripts\python.exe -m pip install -r C:\Academia\app\requirements.txt waitress==3.0.2
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py migrate --noinput
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py collectstatic --noinput
Start-Service AcademiaWeb
```

6. Teste login, um curso e um PDF. Se algo der errado, pare o serviço, volte a pasta `app-anterior` e restaure o banco do backup (veja abaixo).

## Restaurar um backup

1. Pare o site: `Stop-Service AcademiaWeb`.
2. Renomeie `C:\Academia\dados` para `C:\Academia\dados-com-problema` (não apague).
3. Crie de novo `C:\Academia\dados` e copie para dentro dela o `academia.sqlite3` e a pasta `media` do backup escolhido.
4. Reaplique a permissão: `icacls C:\Academia\dados /grant '*S-1-5-19:(OI)(CI)M' /T`.
5. Inicie: `Start-Service AcademiaWeb` e confira `/saude/`, login e um PDF.

Teste a restauração pelo menos uma vez, de preferência numa máquina separada, para garantir que os backups funcionam.

## Problemas comuns

Comandos úteis:

```powershell
Get-Service AcademiaWeb, AcademiaProxy
Get-ChildItem C:\Academia\logs | Sort-Object LastWriteTime -Descending | Select-Object -First 5
curl.exe -s -H "X-Forwarded-Proto: https" http://127.0.0.1:8000/saude/
```

| O que acontece | O que conferir |
|---|---|
| Serviço não inicia | Log `AcademiaWeb` mais recente em `C:\Academia\logs`; nome do `.exe` igual ao do `.xml`; caminho do Python. |
| Funciona no PowerShell mas não como serviço | Permissões do Passo 2, principalmente em `C:\Academia\dados`. |
| `ImproperlyConfigured: Defina DJANGO_SECRET_KEY` | Chave secreta ausente no `ambiente.json`. |
| `JSONDecodeError` | Vírgulas, aspas ou codificação do `ambiente.json`; rode o teste do Passo 5. |
| `database is locked` frequente | Uso simultâneo acima do que o SQLite suporta; avise o responsável pela plataforma. |
| `attempt to write a readonly database` | O serviço não consegue gravar em `C:\Academia\dados`; refaça o `icacls` do Passo 2. |
| Erro 502 | `AcademiaWeb` parado; teste o `/saude/` local. |
| Erro 400 | Endereço do site ausente em `DJANGO_ALLOWED_HOSTS`. |
| Erro 403 CSRF ao entrar | `DJANGO_CSRF_TRUSTED_ORIGINS` deve ser exatamente `https://` + endereço. |
| Página redirecionando sem parar | Cabeçalho `X-Forwarded-Proto` no Caddyfile e `trusted_proxy` no `executar.py`. |
| Site sem cores/visual | Rode `collectstatic` de novo; confira o caminho `/static/*` no Caddyfile. |
| PDF não abre (404) | O arquivo existe em `C:\Academia\dados\media\cursos\pdfs`? |
| HTTPS não é emitido | DNS, encaminhamento das portas 80/443, relógio do servidor; veja o log do `AcademiaProxy`. |
| Funciona só dentro da empresa | DNS público, firewall, NAT ou CGNAT (TI). |
| Funciona só fora da empresa | Falta DNS interno ou retorno de NAT (TI). |
| E-mail não chega | Servidor, porta 587, usuário/senha SMTP, remetente autorizado, caixa de spam. |
| Esqueci a senha do administrador | Rode o comando do Passo 8 de novo. |

Ao pedir suporte, envie os logs, mas **nunca** envie o `ambiente.json` nem o banco.
