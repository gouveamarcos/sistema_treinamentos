# Manual 3 — PostgreSQL no Ubuntu Server

Academia Técnica · Edição de 08/09/2026 · Ubuntu Server **24.04 LTS**, 64 bits.

**Objetivo:** instalar PostgreSQL 16 pelos pacotes do Ubuntu, criar o banco da plataforma e preparar backup e restauração. Banco e aplicação ficarão no mesmo servidor. Leia [Comece aqui](00_LEIA_PRIMEIRO.md) e, ao terminar, siga [Plataforma no Ubuntu](04_PLATAFORMA_UBUNTU.md).

O Ubuntu 24.04 fornece a série 16 em seu repositório. Não adicione repositórios de outra versão do Ubuntu para seguir este manual. [Fonte: pacote oficial](https://packages.ubuntu.com/noble/postgresql-16).

## 1. Entrar no servidor

A TI deve entregar o sistema já instalado e uma conta com permissão `sudo`. Se estiver no console do servidor, faça login normalmente. Para acessar de um computador Windows pela rede autorizada/VPN, abra PowerShell e execute, trocando usuário e IP:

```powershell
ssh SEU_USUARIO@192.168.10.50
```

Na primeira conexão, confirme a identidade/fingerprint do servidor com a TI antes de aceitar. Digite a senha. A partir desse momento, os comandos `bash` deste manual são executados no Ubuntu remoto.

Confira a versão:

```bash
cat /etc/os-release
```

O resultado deve informar Ubuntu e `VERSION_ID="24.04"`. Se for outra versão, não continue usando caminhos fixos deste roteiro.

Quando `sudo` pedir senha, digite a senha de sua conta Ubuntu. Ela não aparece na tela. Isso é diferente de uma senha do PostgreSQL.

## 2. Instalar os pacotes

```bash
sudo apt update
sudo apt install -y postgresql-16 postgresql-client-16
sudo systemctl enable --now postgresql
pg_lsclusters
sudo -u postgres pg_isready
```

Espere `16`, cluster `main`, porta `5432` e estado `online`; depois, `accepting connections`. O serviço geral pode aparecer como `active (exited)` porque administra os clusters. Para o processo do banco, use:

```bash
sudo systemctl status postgresql@16-main --no-pager
```

Se outra instância já ocupar 5432, a instalação pode escolher outra porta. Não altere nem exclua a instância anterior. A TI deve resolver antes de continuar. [Fonte: instalação no Ubuntu](https://documentation.ubuntu.com/server/how-to/databases/install-postgresql/index.html).

## 3. Abrir o console administrativo do banco

```bash
sudo -u postgres psql
```

O prompt deve mudar para `postgres=#`. Você está no programa `psql`; aqui use os blocos `sql`, e não comandos de Linux.

No Ubuntu, a administração local normalmente usa a identidade do usuário Linux `postgres` (`peer`). Não é necessário definir senha para o superusuário do banco nem liberar acesso público para administrá-lo localmente.

## 4. Criar a conta da plataforma e o banco

No `psql`, uma linha por vez:

```sql
CREATE ROLE academia_app WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
SET password_encryption = 'scram-sha-256';
\password academia_app
```

Digite duas vezes uma senha nova e exclusiva, com pelo menos 32 caracteres aleatórios de letras e números. Guarde-a no cofre da empresa. Esse formato evita dificuldades com caracteres especiais na URL de conexão. Depois:

```sql
CREATE DATABASE sistema_treinamentos OWNER academia_app ENCODING 'UTF8' TEMPLATE template0;
\connect sistema_treinamentos
GRANT USAGE, CREATE ON SCHEMA public TO academia_app;
SELECT current_database();
\q
```

Espere `CREATE ROLE`, `CREATE DATABASE`, `GRANT` e o nome do banco. Se já existir algum objeto, confirme sua origem antes de continuar. **Não apague um banco para “resolver” a mensagem.** A conta `academia_app` é dona do banco da plataforma, mas não é superusuária e não pode criar outros bancos.

## 5. Conferir a configuração de acesso local

```bash
sudo -u postgres psql -c 'SHOW config_file;'
sudo -u postgres psql -c 'SHOW hba_file;'
sudo -u postgres psql -c "ALTER SYSTEM SET listen_addresses = 'localhost';"
sudo cp -n /etc/postgresql/16/main/pg_hba.conf /etc/postgresql/16/main/pg_hba.conf.antes-academia
sudo nano /etc/postgresql/16/main/pg_hba.conf
```

Se os caminhos exibidos forem diferentes, use os caminhos reais e confirme com a TI por que a instalação difere deste roteiro.

No editor Nano, procure as regras correspondentes e deixe-as assim. Não substitua o arquivo inteiro nem remova regras de administração:

```text
local   all    postgres                         peer
local   all    all                              peer
host    all    all       127.0.0.1/32            scram-sha-256
host    all    all       ::1/128                 scram-sha-256
```

Para salvar no Nano: pressione `Ctrl + O`, Enter e `Ctrl + X`. Confira se não existe regra anterior permitindo conexões sem senha (`trust`). O PostgreSQL usa a primeira regra que corresponde à conexão. [Fonte: autenticação](https://www.postgresql.org/docs/16/auth-pg-hba-conf.html).

Reinicie e confira:

```bash
sudo systemctl restart postgresql@16-main
sudo -u postgres pg_isready
sudo ss -ltnp 'sport = :5432'
```

O banco deve escutar em `127.0.0.1` e/ou `::1`, não em `0.0.0.0` ou `[::]`. Não abra 5432 no firewall para usuários do site.

Para este roteiro, a aplicação utilizará `DB_SSLMODE=disable` com `127.0.0.1`. Isso se refere somente à conexão dentro do servidor; o site terá HTTPS. O Ubuntu pode oferecer SSL no banco por padrão, mas esta instalação não depende de certificado de banco. Banco em outra máquina exige um projeto próprio de rede privada, autenticação e TLS, não coberto pelos comandos locais.

## 6. Testar a conta da aplicação

```bash
psql -h 127.0.0.1 -p 5432 -U academia_app -d sistema_treinamentos -W
```

Digite a senha criada para `academia_app`. O `-h 127.0.0.1` é importante: escolhe TCP com senha, em vez de autenticação local por usuário Linux. Dentro do `psql`:

```sql
SELECT current_database(), current_user;
BEGIN;
CREATE TABLE public.teste_instalacao_academia (id integer);
INSERT INTO public.teste_instalacao_academia VALUES (1);
SELECT * FROM public.teste_instalacao_academia;
ROLLBACK;
\q
```

Espere o banco correto, o usuário `academia_app` e o valor `1`. O `ROLLBACK` remove a tabela de teste.

Entregue ao instalador: banco `sistema_treinamentos`, usuário `academia_app`, host `127.0.0.1`, porta `5432`, senha por canal reservado e SSL `disable` para esse acesso local.

## 7. Criar o script de backup

O script abaixo roda com `sudo`/root e usa o usuário local `postgres`; não precisa colocar a senha do banco em cron ou no script. Ele guarda o banco em formato de restauração e as definições dos usuários separadamente. PDFs são tratados no manual da plataforma.

```bash
sudo install -d -m 700 /var/backups/academia
sudo nano /usr/local/sbin/backup-postgresql-academia
```

Cole o conteúdo completo:

```bash
#!/bin/bash
set -euo pipefail
umask 077
destino="${1:-/var/backups/academia/$(date +%Y%m%d-%H%M%S)}"
install -d -m 700 "$destino"
sudo -u postgres /usr/lib/postgresql/16/bin/pg_dump -Fc sistema_treinamentos > "$destino/banco.dump"
sudo -u postgres /usr/lib/postgresql/16/bin/pg_dumpall --globals-only > "$destino/usuarios.sql"
/usr/lib/postgresql/16/bin/pg_restore --list "$destino/banco.dump" > "$destino/conteudo-backup.txt"
sha256sum "$destino/banco.dump" > "$destino/banco.sha256"
echo "Backup do banco concluido: $destino"
```

Salve com `Ctrl + O`, Enter, `Ctrl + X`; depois:

```bash
sudo chown root:root /usr/local/sbin/backup-postgresql-academia
sudo chmod 700 /usr/local/sbin/backup-postgresql-academia
sudo /usr/local/sbin/backup-postgresql-academia
sudo ls -lh /var/backups/academia
```

Espere a mensagem de conclusão e uma pasta datada. O `set -e` faz a execução parar em caso de falha; não considere uma pasta parcial como backup concluído. `usuarios.sql` contém definições sensíveis e deve ficar restrito, assim como o dump. [Fontes: backup SQL](https://www.postgresql.org/docs/16/backup-dump.html) e [pg_dump](https://www.postgresql.org/docs/16/app-pgdump.html).

## 8. Restaurar em um banco de teste

Escolha o caminho de uma pasta datada real no comando abaixo. A restauração é feita em **academia_restauracao**, não no banco em uso.

```bash
sudo -u postgres createdb -O academia_app -T template0 academia_restauracao
sudo bash -o pipefail -c 'cat /var/backups/academia/SUBSTITUA_PASTA_DATADA/banco.dump | sudo -u postgres /usr/lib/postgresql/16/bin/pg_restore --dbname=academia_restauracao --no-owner --role=academia_app --no-privileges --exit-on-error --single-transaction'
sudo -u postgres psql -d academia_restauracao -c 'SELECT count(*) FROM django_migrations;'
```

A leitura do dump é feita por root para preservar as permissões restritas da pasta de backups. O processo de restauração se conecta como `postgres` e usa `academia_app` como papel para criar os objetos.

Antes da instalação da plataforma, `django_migrations` ainda não existe. Nesse momento, confira a lista com `sudo -u postgres psql -d academia_restauracao -c '\dt'` e repita este teste depois de instalar a aplicação. Depois das migrações, espere um número de registros maior que zero.

Se o banco de teste já existir, escolha outro nome em todos os comandos. Não use `--clean`, não exclua o banco principal e não restaure por cima de tabelas existentes. Restaurar com `--single-transaction` e `--exit-on-error` evita aceitar uma restauração parcial. [Fonte: pg_restore](https://www.postgresql.org/docs/16/app-pgrestore.html).

Em um servidor novo, recrie o usuário da aplicação pelas seções anteriores. O arquivo `usuarios.sql` é material para a TI recuperar outros papéis se necessário; não o carregue indiscriminadamente em um servidor que já possui usuários.

## 9. Agendamento e conservação

O manual da plataforma cria um backup diário integrado que chama este script e também salva PDFs e configurações. Use esse agendamento ao concluir os dois manuais, sem criar um segundo backup concorrente. Até lá, execute o backup manualmente após mudanças.

Defina uma cópia automática criptografada para outro equipamento ou cofre corporativo. Backup somente neste disco não resolve perda do servidor. Sugestão de retenção a ser validada pela TI: 30 diários e 12 mensais. O script não apaga nada; acompanhe espaço livre com `df -h` e aplique a política de retenção após confirmar a cópia externa.

Uma vez por mês, restaure em banco separado e guarde o resultado. Antes de atualizar versão principal do PostgreSQL, planeje a migração; não misture diretórios de dados de versões diferentes.

## 10. Operação e diagnóstico

```bash
sudo systemctl status postgresql@16-main --no-pager
sudo journalctl -u postgresql@16-main -n 80 --no-pager
sudo tail -n 80 /var/log/postgresql/postgresql-16-main.log
df -h
```

| Erro | O que fazer |
|---|---|
| `Peer authentication failed` para academia_app | Use `-h 127.0.0.1 -W` e a senha da aplicação. |
| `password authentication failed` | Confira a conta e redefina com `sudo -u postgres psql` e `\password academia_app`; atualize a aplicação depois. |
| `connection refused` | Confira `pg_lsclusters`, porta e estado do cluster. |
| `permission denied for schema public` | No banco correto, como postgres, repita o `GRANT` da seção 4. |
| `no pg_hba.conf entry` | Confira arquivo efetivo e regras locais; não libere a internet inteira. |
| Erro ao reiniciar após editar | Confira o log e restaure o arquivo de configuração salvo, com ajuda da TI. |
| `sudo: ... command not found` | Confira instalação dos pacotes e os caminhos da série 16. |
| Espaço insuficiente | Avise a TI; nunca apague arquivos internos de `/var/lib/postgresql` para liberar espaço. |

## 11. Lista de entrega

- [ ] Cluster 16/main online em 5432 e inicialização automática.
- [ ] Conexão restrita ao próprio servidor.
- [ ] Banco UTF-8 e conta da plataforma testados.
- [ ] Senha entregue por canal reservado.
- [ ] Backup executado e restauração de teste conferida.
- [ ] Continuação no manual da plataforma combinada.
