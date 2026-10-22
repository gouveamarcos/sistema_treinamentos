# Apêndice — levar os dados atuais para o servidor

Academia Técnica · 08/09/2026 · Etapa opcional, para transferência de **SQLite para PostgreSQL**.

Se a decisão for começar do zero, pule este apêndice. Se houver técnicos, cursos, resultados ou certificados que precisam continuar existindo, execute uma transferência de homologação primeiro e compare os dados antes de publicar.

## 1. Condições para a transferência

- Origem e destino devem usar a **mesma entrega do código e as mesmas migrações**. Não faça atualização funcional junto com a troca de banco.
- O PostgreSQL de destino deve conter apenas as tabelas criadas por `migrate` e os registros automáticos do Django. Não crie superusuário ou cadastros antes de importar.
- Pare a aplicação de origem e impeça novos acessos durante a exportação definitiva. Se for `runserver` em um terminal, use `Ctrl + C`; se for serviço, a TI deve interrompê-lo. Pare também tarefas que gravem dados.
- Faça backup da origem e da pasta `media`. Não exclua a origem depois de exportar.
- O pacote exportado contém dados pessoais e hashes de senha. Transfira por SFTP, compartilhamento restrito ou outro canal corporativo protegido.

O procedimento abaixo não usa apenas a cópia de `db.sqlite3` no servidor novo: o formato de dados precisa ser convertido pelo Django. As senhas de usuários são preservadas como hashes; não é necessário pedir as senhas aos técnicos.

## 2. Exportar a origem atual em Windows

Exemplo para a cópia atual em `D:\Projetos\sistema_treinamentos`, com ambiente `venv`. Se o responsável pela entrega utiliza outro caminho, ele deve substituir os caminhos antes de executar.

Na máquina de origem, crie `C:\TransferenciaAcademia` pelo Explorador. Em Bloco de Notas, crie `C:\TransferenciaAcademia\exportar_sqlite.py`, codificação UTF-8, com este conteúdo:

```python
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import sys

origem = Path(r"D:\Projetos\sistema_treinamentos")
destino = Path(r"C:\TransferenciaAcademia\exportacao")
banco = origem / "db.sqlite3"
if not banco.is_file():
    raise SystemExit("db.sqlite3 nao encontrado; confira a origem.")
if destino.exists():
    raise SystemExit("Pasta exportacao ja existe. Guarde-a e escolha outro destino.")
sys.path.insert(0, str(origem))
os.environ["DJANGO_SETTINGS_MODULE"] = "treinamentos.settings"
from django.conf import settings
settings.DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": f"file:{banco.as_posix()}?mode=ro",
        "OPTIONS": {"uri": True},
    }
}
import django
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
executor = MigrationExecutor(connection)
if executor.migration_plan(executor.loader.graph.leaf_nodes()):
    raise SystemExit("Origem com migracoes pendentes; alinhe a entrega antes de exportar.")
from django.core.management import call_command
destino.mkdir()
call_command(
    "dumpdata",
    use_natural_foreign_keys=True,
    use_natural_primary_keys=True,
    exclude=["contenttypes", "auth.permission", "sessions.session", "admin.logentry"],
    indent=2,
    output=str(destino / "dados.json"),
)
registros = json.loads((destino / "dados.json").read_text(encoding="utf-8"))
contagens = dict(sorted(Counter(item["model"] for item in registros).items()))
(destino / "contagens.json").write_text(
    json.dumps(contagens, ensure_ascii=False, indent=2), encoding="utf-8"
)
if (origem / "media").exists():
    shutil.copytree(origem / "media", destino / "media")
else:
    (destino / "media").mkdir()
print("Exportacao concluida em", destino)
print(json.dumps(contagens, ensure_ascii=False, indent=2))
```

No PowerShell, execute:

```powershell
& D:\Projetos\sistema_treinamentos\venv\Scripts\python.exe -B C:\TransferenciaAcademia\exportar_sqlite.py
```

O script abre o SQLite explicitamente em modo de leitura, sem depender da variável de banco do ambiente. O resultado deve ser uma pasta `exportacao` com `dados.json`, `contagens.json` e `media`. Se houver erro, não aceite a pasta parcial como transferência concluída; preserve-a para diagnóstico e repita para outro destino depois de resolver.

As chaves naturais evitam depender dos IDs de grupos e permissões gerados automaticamente no destino. Sessões de login e o log específico do Django Admin são excluídos; os usuários farão novo login. **Eventos de auditoria do modelo `core.EventoAuditoria` são incluídos.** [Fontes: dumpdata](https://docs.djangoproject.com/en/6.0/ref/django-admin/#dumpdata) e [chaves naturais](https://docs.djangoproject.com/en/6.0/topics/serialization/#natural-keys).

Se a origem já for PostgreSQL, use `pg_dump`/`pg_restore` dos manuais de banco e uma cópia coerente de `media`, em vez deste exportador SQLite. Não use este script para localizar ou adivinhar um banco diferente.

## 3. Importar no Windows Server

Conclua as etapas de configuração e `migrate` do manual Windows, mas **não** `createsuperuser`. Mantenha `AcademiaWeb` parado se já tiver sido instalado. Copie a pasta exportada para `C:\Academia\transferencia`. O arquivo deve ficar em `C:\Academia\transferencia\dados.json`.

```powershell
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py loaddata C:\Academia\transferencia\dados.json
if ($LASTEXITCODE -ne 0) { throw 'Importacao falhou. Nao liberar o sistema.' }
robocopy.exe C:\Academia\transferencia\media C:\Academia\app\media /E /COPY:DAT /R:2 /W:2
if ($LASTEXITCODE -ge 8) { throw 'Falha na copia de PDFs.' }
icacls C:\Academia\app\media /grant '*S-1-5-19:(OI)(CI)M' /T
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py collectstatic --noinput
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py check
```

Espere `Installed ... object(s)` sem erros. Guarde a contagem informada. Não reaplique o JSON em um banco que já recebeu uso real. Se já houver dados no destino, a TI deve escolher um banco novo para o teste, sem sobrescrever o existente.

## 4. Importar no Ubuntu Server

Conclua a configuração, comando `academia-manage` e `migrate`, antes de `createsuperuser`. Envie a pasta exportada por SFTP à pasta pessoal do instalador, por exemplo `/home/SEU_USUARIO/exportacao`. Prepare uma cópia restrita legível pela conta da aplicação:

```bash
sudo install -d -m 750 -o root -g academia /srv/academia/transferencia
sudo cp -a /home/SEU_USUARIO/exportacao/. /srv/academia/transferencia/
sudo chown -R root:academia /srv/academia/transferencia
sudo chmod -R u=rwX,g=rX,o= /srv/academia/transferencia
sudo academia-manage loaddata /srv/academia/transferencia/dados.json
```

Só continue se a importação terminar sem erro:

```bash
sudo cp -a /srv/academia/transferencia/media/. /srv/academia/app/media/
sudo chown -R academia:caddy /srv/academia/app/media
sudo find /srv/academia/app/media -type d -exec chmod 2750 {} +
sudo find /srv/academia/app/media -type f -exec chmod 640 {} +
sudo academia-manage collectstatic --noinput
sudo academia-manage check
```

## 5. Conferir os registros

No destino, use este código como argumento de `shell -c` do comando administrativo da plataforma:

```python
from django.apps import apps; import json; print(json.dumps({m._meta.label_lower: m.objects.count() for m in apps.get_models() if m._meta.app_label == 'core' or m._meta.label_lower in ('auth.user', 'auth.group')}, indent=2))
```

Exemplo completo no Ubuntu:

```bash
sudo academia-manage shell -c "from django.apps import apps; import json; print(json.dumps({m._meta.label_lower: m.objects.count() for m in apps.get_models() if m._meta.app_label == 'core' or m._meta.label_lower in ('auth.user', 'auth.group')}, indent=2))"
```

Exemplo completo no Windows:

```powershell
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py shell -c "from django.apps import apps; import json; print(json.dumps({m._meta.label_lower: m.objects.count() for m in apps.get_models() if m._meta.app_label == 'core' or m._meta.label_lower in ('auth.user', 'auth.group')}, indent=2))"
```

Compare cada modelo com `contagens.json`. Modelo ausente na origem tinha zero registros exportados. Cadastros automáticos de grupos devem ser reconciliados pela chave natural; diferenças precisam ser investigadas, não aceitas automaticamente.

Além das quantidades:

1. Entre com um administrador já existente. Se o acesso foi perdido, use `redefinir_admin` conforme o manual do sistema.
2. Confira uma empresa, um técnico e suas liberações.
3. Abra pelo menos um PDF e um certificado que já existiam antes da transferência.
4. Compare código, data de conclusão e validade de certificados.
5. Faça um novo cadastro de homologação para confirmar que a geração de IDs segue funcionando.
6. Confirme primeiro acesso e recuperação de senha com uma conta controlada.

Não altere senhas de todos os usuários para “testar”. Nunca permita origem e destino recebendo cadastros novos ao mesmo tempo durante a mudança definitiva.

## 6. Concluir a mudança

Após aceite, faça backup completo do PostgreSQL e arquivos do destino, publique o domínio e mantenha a origem preservada e fora de uso pelo prazo definido pela empresa. Se o teste falhar, mantenha o destino fechado e retome a origem intacta; combine a janela para não perder dados feitos após a transferência.

Guarde exportações em local restrito e retire cópias transitórias do servidor seguindo a política de retenção da TI. Esse pacote não deve ficar em uma pasta pública ou ser enviado junto dos manuais a usuários finais.
