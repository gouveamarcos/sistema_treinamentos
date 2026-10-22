# Manual 2 — Trazer os dados atuais

Academia Técnica · Edição de 22/10/2026 · Use somente se for preciso manter cadastros, cursos e certificados que já existem.

A plataforma atual e o servidor novo usam **SQLite**, então a transferência é uma cópia de dois itens:

| Item | Na máquina atual | No servidor |
|---|---|---|
| Banco de dados | `D:\Projetos\sistema_treinamentos\db.sqlite3` | `C:\Academia\dados\academia.sqlite3` |
| PDFs dos cursos | `D:\Projetos\sistema_treinamentos\media\` | `C:\Academia\dados\media\` |

Os técnicos continuam com as mesmas senhas. A senha do administrador pode ser trocada no Passo 8 do Manual 1, caso ninguém lembre dela.

Faça esta etapa **no Passo 7 do Manual 1**, antes de criar o administrador e antes de cadastrar qualquer coisa no servidor.

## 1. Na máquina atual: preparar a cópia

1. **Desligue a plataforma.** Se ela estiver rodando num terminal (`runserver`), clique na janela e pressione `Ctrl + C`. Copiar o banco com a plataforma ligada pode gerar uma cópia corrompida.
2. Confira que, na pasta `D:\Projetos\sistema_treinamentos`, **não** existem os arquivos `db.sqlite3-wal` nem `db.sqlite3-journal`. Se existirem, a plataforma ainda está ligada ou foi fechada no meio de uma gravação: ligue e desligue de novo com `Ctrl + C`.
3. Copie para um pendrive ou pasta de rede protegida:
   - o arquivo `db.sqlite3`;
   - a pasta `media` inteira (se ela não existir, nenhum PDF foi enviado ainda).
4. Guarde também uma cópia desses itens na própria máquina, como garantia. Não apague nada da origem.

Os arquivos contêm dados pessoais e senhas criptografadas dos usuários. Transfira por um meio protegido e apague a cópia do pendrive depois.

## 2. No servidor: colocar os dados no lugar

Garanta que o site não está rodando (na primeira instalação ele ainda não existe; numa reinstalação, pare-o):

```powershell
if (Get-Service AcademiaWeb -ErrorAction SilentlyContinue) { Stop-Service AcademiaWeb }
```

Pelo Explorador:

1. Copie o `db.sqlite3` para `C:\Academia\dados\` e **renomeie** para `academia.sqlite3`.
2. Copie **o conteúdo** da pasta `media` (a subpasta `cursos`) para dentro de `C:\Academia\dados\media\`. O resultado deve ser `C:\Academia\dados\media\cursos\pdfs\...`.

Reaplique as permissões (arquivos copiados podem chegar com outras permissões):

```powershell
icacls C:\Academia\dados /grant '*S-1-5-19:(OI)(CI)M' /T
Test-Path C:\Academia\dados\academia.sqlite3
```

**Resultado esperado:** `True`.

## 3. Conferir e atualizar o banco

```powershell
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py migrate --noinput
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py shell -c "from core.models import Empresa, Tecnico, Curso, ConclusaoTreinamento; from django.contrib.auth.models import User; print('Usuarios:', User.objects.count()); print('Empresas:', Empresa.objects.count()); print('Tecnicos:', Tecnico.objects.count()); print('Cursos:', Curso.objects.count()); print('Certificados:', ConclusaoTreinamento.objects.count())"
```

**Resultado esperado:** o `migrate` termina sem erro (pode dizer `No migrations to apply`). As contagens devem bater com o que existe na plataforma atual.

Confira se os PDFs vieram junto:

```powershell
& C:\Academia\venv\Scripts\python.exe C:\Academia\operacao\executar.py shell -c "from core.models import Curso; faltando=[c.nome for c in Curso.objects.exclude(material_pdf='').exclude(material_pdf=None) if not c.material_pdf.storage.exists(c.material_pdf.name)]; print('PDFs faltando:', faltando or 'nenhum')"
```

**Resultado esperado:** `PDFs faltando: nenhum`. Se aparecer algum curso, copie de novo a pasta `media`.

## 4. Voltar ao Manual 1

Continue no **Passo 8 do Manual 1**. Lá você redefine a senha do administrador (`redefinir_admin`); os demais usuários mantêm as senhas que já tinham.

Depois que o site estiver no ar, a máquina antiga **não deve mais ser usada** para cadastros: o que for feito nela não chega ao servidor.

## Dados de teste

Se o banco atual tiver cadastros de teste (empresas, técnicos ou cursos criados só para experimentar), remova-os pelo painel `/admin/` depois da instalação, ou comece com o banco vazio (Caminho A do Passo 7) e cadastre tudo de novo.
