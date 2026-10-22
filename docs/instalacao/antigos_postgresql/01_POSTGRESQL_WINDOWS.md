# Manual 1 — PostgreSQL no Windows Server

Academia Técnica · Edição de 08/09/2026 · Windows Server 2022/2025 com interface gráfica, x64.

**Objetivo:** instalar PostgreSQL 18, criar o banco e o usuário da plataforma e preparar backup e restauração. O PostgreSQL ficará na mesma máquina da aplicação. Reserve aproximadamente uma hora, além do tempo de download e validação. Não instale uma segunda instância se a TI já disponibilizou um banco: peça os dados de conexão e adapte com ela.

Leia primeiro a ficha de infraestrutura em [Comece aqui](00_LEIA_PRIMEIRO.md). Depois deste manual, execute [Plataforma no Windows](02_PLATAFORMA_WINDOWS.md).

## 1. Abrir as ferramentas certas

1. Entre no servidor com uma conta administradora autorizada.
2. Abra o menu Iniciar, digite **Windows PowerShell**, clique com o botão direito e escolha **Executar como administrador**.
3. Confirme a solicitação do Windows. Mantenha essa janela aberta.
4. Para conferir a versão do Windows, pressione `Windows + R`, digite `winver` e pressione Enter.

Neste manual, blocos `powershell` vão para essa janela. Blocos `sql` vão somente para o programa `psql`, aberto nos passos indicados.

## 2. Baixar e instalar

1. No servidor, abra a [página oficial de instaladores Windows](https://www.postgresql.org/download/windows/).
2. Siga o link do instalador EDB e escolha **PostgreSQL 18, Windows x86-64**, na atualização corretiva disponível da série 18. Não escolha beta/RC nem pacote ZIP de binários.
3. Execute o instalador como administrador.
4. Na pasta de instalação, mantenha `C:\Program Files\PostgreSQL\18`.
5. Mantenha **PostgreSQL Server**, **Command Line Tools** e **pgAdmin 4**. Stack Builder não é necessário para esta plataforma.
6. Mantenha o diretório de dados sugerido pelo instalador e anote o caminho. Ele guarda os arquivos internos do banco; não deve ser movido manualmente.
7. Defina uma senha forte para o administrador do banco, chamado `postgres`. Guarde-a no cofre da empresa. Essa senha é diferente da senha do futuro administrador do site.
8. Mantenha a porta **5432**. Se estiver ocupada, pare e confirme com a TI se já existe PostgreSQL instalado.
9. Na localização/locale, mantenha o padrão. O banco da aplicação será criado explicitamente com UTF-8.
10. Conclua a instalação. Desmarque a execução do Stack Builder no final.

**Resultado esperado:** instalação concluída sem erros. Os instaladores da série 18 têm Windows Server 2022/2025 entre as plataformas de referência informadas pelo fornecedor. [Fonte: instaladores PostgreSQL](https://www.postgresql.org/download/windows/).

## 3. Verificar o serviço e a porta

No PowerShell administrativo:

```powershell
Get-Service -Name '*postgres*'
& 'C:\Program Files\PostgreSQL\18\bin\pg_isready.exe' -h 127.0.0.1 -p 5432
```

Espere um serviço com estado `Running` e a mensagem `accepting connections`. O nome usual é `postgresql-x64-18`; se a instalação mostrar outro, use o nome real nos comandos seguintes e no manual da plataforma.

Abra `services.msc` pelo menu Iniciar. Localize o serviço PostgreSQL, abra suas propriedades e confira **Tipo de inicialização: Automático**. Não altere a conta usada pelo serviço do PostgreSQL.

## 4. Criar um usuário exclusivo e o banco

Abra o terminal do banco:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -h 127.0.0.1 -p 5432 -U postgres -d postgres -W
```

Digite a senha do administrador `postgres`. O prompt deve passar a ser `postgres=#`. Nesse prompt, execute uma linha de cada vez:

```sql
CREATE ROLE academia_app WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
SET password_encryption = 'scram-sha-256';
\password academia_app
```

O último comando pergunta a nova senha duas vezes. Crie uma senha exclusiva de pelo menos 32 caracteres aleatórios, usando letras e números. Isso simplifica a montagem da URL de conexão nos passos seguintes. Não reutilize a senha de `postgres`.

Depois execute:

```sql
CREATE DATABASE sistema_treinamentos OWNER academia_app ENCODING 'UTF8' TEMPLATE template0;
\connect sistema_treinamentos
GRANT USAGE, CREATE ON SCHEMA public TO academia_app;
SELECT current_database();
\q
```

**Resultado esperado:** `CREATE ROLE`, `CREATE DATABASE`, `GRANT` e o nome `sistema_treinamentos`. A aplicação usa `academia_app`; não precisa ser superusuária do PostgreSQL. O administrador `postgres` continua reservado à administração do banco.

Se aparecer `already exists`, não exclua nada: confirme se é uma instalação iniciada anteriormente. Para continuar, primeiro verifique proprietário e conteúdo com a TI.

## 5. Limitar a conexão ao próprio servidor

Volte ao `psql` como `postgres`, usando o comando da seção 4. Execute:

```sql
SHOW config_file;
SHOW hba_file;
ALTER SYSTEM SET listen_addresses = 'localhost';
\q
```

Anote os caminhos exibidos. O `pg_hba.conf` decide quem pode conectar e como comprova a senha. Abra o **Bloco de Notas como administrador**, use Arquivo → Abrir → Todos os arquivos e selecione o caminho de `pg_hba.conf` que foi mostrado. Faça uma cópia de segurança desse arquivo antes de editar.

Localize as regras `host` do endereço `127.0.0.1/32` e `::1/128`. Elas devem usar `scram-sha-256`, como abaixo:

```text
host    all    all    127.0.0.1/32    scram-sha-256
host    all    all    ::1/128         scram-sha-256
```

Preserve os comentários e as demais regras de manutenção. Em uma instalação nova dedicada, não deve haver regra `trust` nem liberação para `0.0.0.0/0`. A primeira regra correspondente é a utilizada; acrescentar uma regra segura no final não corrige uma regra permissiva anterior. [Fonte: pg_hba.conf](https://www.postgresql.org/docs/18/auth-pg-hba-conf.html).

Salve e reinicie o banco, antes de a plataforma estar em uso:

```powershell
Restart-Service -Name postgresql-x64-18
& 'C:\Program Files\PostgreSQL\18\bin\pg_isready.exe' -h 127.0.0.1 -p 5432
```

Não abra a porta 5432 no roteador para os técnicos. A conexão interna deste roteiro usa `127.0.0.1` e `DB_SSLMODE=disable`; o HTTPS dos usuários é uma conexão separada. Se banco e aplicação forem para máquinas diferentes, este modelo precisa ser adaptado com IP privado, firewall e TLS verificado; não basta trocar `localhost` por `*`.

## 6. Testar usando a conta da aplicação

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -h 127.0.0.1 -p 5432 -U academia_app -d sistema_treinamentos -W
```

Digite a senha de `academia_app`, não a de `postgres`. No `psql`:

```sql
SELECT current_database(), current_user;
BEGIN;
CREATE TABLE public.teste_instalacao_academia (id integer);
INSERT INTO public.teste_instalacao_academia VALUES (1);
SELECT * FROM public.teste_instalacao_academia;
ROLLBACK;
\q
```

O resultado deve mostrar banco `sistema_treinamentos`, usuário `academia_app` e o número `1`. O `ROLLBACK` desfaz a tabela de teste. Esse teste confirma leitura, escrita e criação de tabelas, necessárias para as migrações.

Entregue ao instalador da aplicação: host `127.0.0.1`, porta `5432`, banco `sistema_treinamentos`, usuário `academia_app`, senha por canal reservado e modo SSL `disable` para essa conexão local.

## 7. Preparar o backup

O banco não contém o conteúdo dos PDFs: guarda o caminho deles. Por isso o backup completo também precisa da pasta `media`, do código entregue e da configuração, cobertos no manual da plataforma.

No PowerShell administrativo, crie as pastas e restrinja o acesso a administradores e SYSTEM. Os identificadores numéricos funcionam em Windows em português ou inglês:

```powershell
New-Item -ItemType Directory -Force -Path C:\Academia\backup,C:\Academia\backups | Out-Null
icacls C:\Academia\backup /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F'
icacls C:\Academia\backups /inheritance:r /grant:r '*S-1-5-32-544:(OI)(CI)F' '*S-1-5-18:(OI)(CI)F'
notepad C:\Academia\backup\pgpass.conf
```

Salve uma única linha no arquivo aberto, substituindo a senha:

```text
127.0.0.1:5432:*:academia_app:SUBSTITUA_PELA_SENHA_DO_BANCO
```

Esse arquivo permite ao backup funcionar sem alguém digitando a senha. Se usou caracteres `:` ou `\` na senha, eles precisam ser escapados nesse formato; com senha alfanumérica não há esse problema. [Fonte: arquivo de senha PostgreSQL](https://www.postgresql.org/docs/18/libpq-pgpass.html).

Abra `notepad C:\Academia\backup\Backup-Banco.ps1`, cole o conteúdo completo abaixo e salve como **Todos os arquivos**, sem `.txt` no final:

```powershell
param([string]$Destino = '')
$ErrorActionPreference = 'Stop'
if (-not $Destino) {
    $Destino = Join-Path 'C:\Academia\backups' (Get-Date -Format 'yyyyMMdd-HHmmss')
}
New-Item -ItemType Directory -Force -Path $Destino | Out-Null
$env:PGPASSFILE = 'C:\Academia\backup\pgpass.conf'
$PgBin = 'C:\Program Files\PostgreSQL\18\bin'
$Arquivo = Join-Path $Destino 'banco.dump'
& "$PgBin\pg_dump.exe" -h 127.0.0.1 -p 5432 -U academia_app -d sistema_treinamentos -w -Fc -f $Arquivo
if ($LASTEXITCODE -ne 0) { throw 'Falha no pg_dump. Backup incompleto.' }
& "$PgBin\pg_restore.exe" --list $Arquivo | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Arquivo de backup nao passou na leitura.' }
Get-FileHash -LiteralPath $Arquivo -Algorithm SHA256 | Format-List | Out-File (Join-Path $Destino 'banco.sha256.txt')
'Backup do banco concluido: ' + $Destino
```

Execute:

```powershell
powershell.exe -NoProfile -ExecutionPolicy RemoteSigned -File C:\Academia\backup\Backup-Banco.ps1
```

**Resultado esperado:** mensagem de conclusão e pasta datada com `banco.dump` e seu hash. Conferir a lista não substitui restaurar: faça a seção seguinte. Se a política corporativa bloquear scripts, a TI deve assiná-los/aprová-los; não desative a política global.

O formato `-Fc` é restaurado por `pg_restore`. O dump deste banco não inclui a criação de usuários PostgreSQL; em uma recuperação em servidor novo, recrie `academia_app` pelas seções 2 a 4. [Fontes: pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html) e [pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html).

## 8. Testar a restauração sem tocar no banco principal

Escolha uma pasta de backup real no lugar do exemplo abaixo. No PowerShell:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\createdb.exe' -h 127.0.0.1 -U postgres -W -O academia_app -T template0 academia_restauracao
$env:PGPASSFILE = 'C:\Academia\backup\pgpass.conf'
& 'C:\Program Files\PostgreSQL\18\bin\pg_restore.exe' -h 127.0.0.1 -U academia_app -d academia_restauracao -w --no-owner --no-privileges --exit-on-error --single-transaction 'C:\Academia\backups\SUBSTITUA_PASTA_DATADA\banco.dump'
if ($LASTEXITCODE -ne 0) { throw 'Restauracao falhou; nao usar este banco.' }
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -h 127.0.0.1 -U academia_app -d academia_restauracao -w -c 'SELECT count(*) FROM django_migrations;'
```

Se a plataforma ainda não foi instalada, `django_migrations` não existirá; neste primeiro teste use `\dt` no `psql` para conferir a lista vazia e repita o teste depois das migrações. Após a instalação, a consulta deve mostrar um número maior que zero.

Se `academia_restauracao` já existir, escolha um novo nome em **todos** os comandos desse teste. Não restaure por cima de um banco com tabelas. Não use `--clean` nem exclua o banco principal.

Guarde o resultado do teste. A restauração funcional da aplicação, incluindo PDFs, é descrita no manual da plataforma.

## 9. Agendamento e rotina

Para a plataforma completa, use o agendamento de backup integrado do manual seguinte, que chama este script e inclui arquivos. **Não crie dois agendamentos no mesmo horário.** Se estiver instalando apenas o banco por enquanto, execute o script manualmente ao concluir o trabalho e ao entregar a máquina.

Defina uma rotina com a TI: backup diário; cópia diária criptografada fora do servidor; conferir falhas e espaço livre; testar restauração mensalmente e antes de atualizações relevantes. Uma sugestão inicial é reter 30 cópias diárias e 12 mensais, ajustando à política da empresa. Os scripts não apagam cópias automaticamente.

Não copie simplesmente a pasta interna de dados do PostgreSQL enquanto ele está rodando para substituir `pg_dump`. Em troca de versão principal, por exemplo 18 para 19, a TI deve planejar migração e restauração; atualizar binários não converte automaticamente os dados.

## 10. Problemas comuns

| Mensagem/sintoma | Conferir e agir |
|---|---|
| `password authentication failed` | Nome do usuário, senha correta e `pgpass.conf`. Teste com `psql -W` para separar erro de senha e erro no arquivo. |
| `connection refused` | Serviço parado, porta errada ou configuração `listen_addresses`. Repita a seção 3. |
| `no pg_hba.conf entry` | Confira o arquivo efetivo com `SHOW hba_file`; use `127.0.0.1`, não o IP público. |
| `permission denied for schema public` | Conecte como `postgres` ao banco correto e repita o `GRANT` da seção 4. |
| Porta 5432 ocupada | Identifique a instância existente com a TI antes de instalar outra. |
| Backup pede senha em tarefa automática | Confirme `PGPASSFILE`, nome do arquivo sem `.txt` e acesso de SYSTEM. |
| `server version mismatch` no dump | Use as ferramentas da versão 18 para o servidor 18. Ferramenta mais antiga pode recusar servidor novo. |
| Disco cheio | Suspenda importações, avise a TI e amplie espaço/gerencie backups já copiados; não apague arquivos internos do banco. |

## 11. Lista de entrega do PostgreSQL

- [ ] Serviço ativo e automático.
- [ ] Porta 5432 apenas local, sem publicação na internet.
- [ ] Banco UTF-8 e usuário `academia_app` testados.
- [ ] Senhas guardadas fora deste manual.
- [ ] Script de backup executado com sucesso.
- [ ] Restauração de teste conferida.
- [ ] Instalador da plataforma recebeu os dados de conexão.
