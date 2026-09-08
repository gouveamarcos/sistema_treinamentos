# Manual do Superadmin

Manual completo para administração da Academia Técnica Sem Parar.

## 1. Papel do superadmin

O superadmin é o usuário com acesso total à plataforma.

Ele pode:

- cadastrar empresas;
- cadastrar técnicos;
- cadastrar responsáveis;
- definir papéis de acesso;
- criar produtos, cursos, etapas, questões e alternativas;
- liberar cursos;
- importar dados por CSV;
- acompanhar relatórios;
- consultar histórico de auditoria;
- redefinir acesso administrativo;
- preparar a operação para produção.

Use este perfil com cuidado. Para atividades do dia a dia, prefira criar
responsáveis com papéis específicos.

## 2. Acesso administrativo

O superadmin pode acessar:

```text
/admin/
```

E também as telas operacionais:

```text
/
/empresas/
/tecnicos/
/responsaveis/
/catalogo/produtos/
/catalogo/cursos/
/liberacoes/lote/
/relatorios/treinamentos/
/historico/
```

## 3. Recuperar ou redefinir acesso do superadmin

Se perder o acesso administrativo, use o comando:

```powershell
.\venv\Scripts\python.exe manage.py redefinir_admin --username admin --email seu.email@empresa.com
```

O comando solicita uma nova senha no terminal.

Em automações seguras, também é possível usar:

```powershell
.\venv\Scripts\python.exe manage.py redefinir_admin --username admin --email seu.email@empresa.com --password "NOVA-SENHA" --noinput
```

Evite deixar senhas registradas em histórico de terminal.

## 4. Estrutura operacional recomendada

Antes de cadastrar cursos, siga esta ordem:

1. Criar empresas.
2. Criar técnicos.
3. Criar produtos.
4. Criar cursos.
5. Criar etapas dos cursos.
6. Criar questões e alternativas.
7. Criar responsáveis operacionais ou editores.
8. Liberar cursos para técnicos.
9. Acompanhar relatórios e auditoria.

## 5. Empresas

Acesse:

```text
/empresas/
```

Use a tela para cadastrar e editar empresas/clientes.

Campos principais:

- nome;
- documento;
- responsável;
- e-mail;
- telefone;
- status ativo/inativo.

Somente superadmin deve criar ou inativar empresas. Responsáveis comuns devem
atuar apenas nas empresas atribuídas a eles.

## 6. Técnicos

Acesse:

```text
/tecnicos/
```

Campos principais:

- empresa;
- nome;
- e-mail;
- matrícula;
- telefone;
- equipe;
- região;
- status ativo/inativo.

O e-mail e a matrícula são usados no primeiro acesso do técnico.

### Importar técnicos por CSV

Na tela de técnicos, use a importação CSV.

Colunas esperadas:

```text
nome,email,matricula,telefone,equipe,regiao,ativo
```

Exemplo:

```csv
nome,email,matricula,telefone,equipe,regiao,ativo
João Silva,joao@empresa.com,TEC001,11999999999,Campo,Sudeste,sim
Maria Souza,maria@empresa.com,TEC002,11888888888,Campo,Sul,nao
```

Regras:

- `nome`, `email` e `matricula` são obrigatórios;
- o arquivo deve ser `.csv`;
- há limite de tamanho configurado por `MAX_CSV_IMPORT_SIZE_BYTES`;
- erros impedem a gravação parcial das linhas válidas.

## 7. Responsáveis por empresa

Acesse:

```text
/responsaveis/
```

Use esta tela para dar acesso a outras pessoas.

Papéis disponíveis:

- **Responsável operacional**: gerencia operação da empresa, técnicos,
  liberações, relatórios e histórico operacional.
- **Editor de cursos**: gerencia produtos, cursos, etapas, questões e
  alternativas.

Ao cadastrar um responsável, o sistema envia convite por e-mail para definição
de senha. Também é possível reenviar o convite. Por padrão, o link fica válido
por 7 dias, conforme `PASSWORD_RESET_TIMEOUT`.

## 8. Produtos

Acesse:

```text
/catalogo/produtos/
```

Produto é o agrupador de cursos. Exemplos:

- Sem Parar;
- Abastece;
- Tag;
- Equipamentos;
- Procedimentos operacionais.

Campos principais:

- nome;
- descrição;
- ativo/inativo.

## 9. Cursos

Acesse:

```text
/catalogo/cursos/
```

Campos principais:

- produto;
- nome;
- descrição;
- validade em meses;
- nota mínima;
- link NotebookLM, se houver;
- ativo/inativo.

### Validade

Use validade em meses quando o treinamento exige reciclagem periódica.

Exemplo:

- validade `12`: certificado vence em 12 meses;
- validade vazia ou zero: certificado sem vencimento.

### Nota mínima

Define o percentual mínimo para aprovação em prova.

Exemplo:

```text
70
```

significa aprovação com 70% ou mais.

## 10. Construtor de conteúdo

Dentro da lista de cursos, acesse o conteúdo do curso.

Tipos de etapa:

- **Texto**: conteúdo escrito;
- **Vídeo**: videoaula por link incorporado;
- **Teste**: avaliação intermediária;
- **Prova final**: avaliação de conclusão.

Campos da etapa:

- título;
- descrição;
- tipo;
- ordem;
- conteúdo;
- URL do vídeo;
- ativo/inativo.

## 11. Videoaulas

Para vídeos, use preferencialmente YouTube em modo **Não listado**.

Cadastre o link no formato incorporável:

```text
https://www.youtube.com/embed/ID_DO_VIDEO
```

Evite cadastrar:

```text
https://www.youtube.com/watch?v=ID_DO_VIDEO
```

Se receber o link comum do YouTube, converta:

```text
https://www.youtube.com/watch?v=abc123
```

para:

```text
https://www.youtube.com/embed/abc123
```

Não é recomendado hospedar MP4 diretamente no servidor da aplicação em produção,
pois vídeo consome armazenamento, banda e backup.

## 12. Questões e alternativas

Em etapas do tipo teste ou prova, cadastre questões.

Para cada questão:

1. Informe o enunciado.
2. Defina a ordem.
3. Cadastre alternativas.
4. Marque uma alternativa como correta.

Boas práticas:

- escreva perguntas objetivas;
- evite alternativas ambíguas;
- mantenha apenas uma resposta correta;
- revise a ordem das questões;
- teste o curso antes de liberar para muitos técnicos.

## 13. Liberação de cursos

Acesse:

```text
/liberacoes/lote/
```

Você pode liberar cursos:

- para técnicos selecionados;
- para todos os técnicos ativos de uma empresa;
- como obrigatório ou opcional.

Ao liberar um curso já existente para o técnico, o sistema evita duplicidade e
reativa liberações inativas quando aplicável.

## 14. Importar liberações por CSV

Use quando precisar liberar cursos para muitos técnicos.

Colunas aceitas:

```text
matricula,email,obrigatorio
```

Exemplo:

```csv
matricula,email,obrigatorio
TEC001,,sim
,maria@empresa.com,nao
```

Regras:

- informe matrícula ou e-mail;
- o técnico precisa pertencer à empresa selecionada;
- o arquivo deve ser `.csv`;
- há limite de tamanho configurado;
- erros impedem gravação parcial.

## 15. Relatórios gerenciais

Acesse:

```text
/relatorios/treinamentos/
```

O relatório mostra:

- total de liberações;
- pendentes;
- em andamento;
- em dia;
- vencendo em até 30 dias;
- vencidos;
- risco por empresa;
- risco por curso;
- lista detalhada por técnico e curso.

Filtros:

- empresa;
- situação.

Também é possível exportar CSV para análise externa.

## 16. Histórico e auditoria

Acesse:

```text
/historico/
```

O histórico registra eventos administrativos, como:

- cadastros;
- edições;
- mudanças de status;
- importações;
- liberações;
- convites enviados.

Use filtros por empresa, ação e busca textual.

## 17. Validação de certificados

A validação pública fica em:

```text
/certificados/validar/
```

O código tem formato:

```text
CERT-XXXXXXXX
```

Use essa tela para confirmar autenticidade de certificados apresentados por
técnicos, parceiros ou clientes.

## 18. Lembretes de reciclagem

Para enviar lembretes de certificações vencidas ou próximas do vencimento:

```powershell
.\venv\Scripts\python.exe manage.py enviar_lembretes_reciclagem
```

Para alterar a janela:

```powershell
.\venv\Scripts\python.exe manage.py enviar_lembretes_reciclagem --dias 15
```

Em produção, agende a execução diária.

## 19. Saúde da aplicação

Endpoint público:

```text
/saude/
```

Resposta esperada:

```json
{"status": "ok", "database": "ok"}
```

Se o banco estiver indisponível, retorna erro HTTP 503.

## 20. Produção e PostgreSQL

Para produção, configure no ambiente:

```text
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=uma-chave-longa-e-secreta
DJANGO_ALLOWED_HOSTS=treinamentos.suaempresa.com.br
DJANGO_CSRF_TRUSTED_ORIGINS=https://treinamentos.suaempresa.com.br
DATABASE_URL=postgres://usuario:senha@host:5432/sistema_treinamentos
```

Depois execute:

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check --deploy
```

Consulte também:

```text
deploy/PRODUCTION.md
```

## 21. Backup e restauração

Para exportar dados:

```bash
python manage.py dumpdata --exclude auth.permission --exclude contenttypes --indent 2 > backup.json
```

Para restaurar:

```bash
python manage.py loaddata backup.json
```

Em produção com PostgreSQL, prefira também backups nativos do provedor.

## 22. Boas práticas de administração

- Use superadmin somente quando necessário.
- Crie responsáveis com papéis específicos.
- Revise cursos antes de liberar.
- Teste videoaulas em janela anônima.
- Monitore cursos vencidos semanalmente.
- Exporte relatórios antes de reuniões operacionais.
- Mantenha backups.
- Não publique senhas no GitHub.
- Use vídeos não listados no YouTube ou serviço profissional de vídeo.
- Monitore `/saude/`.

## 23. Checklist de implantação

Antes de considerar o ambiente pronto:

- `DJANGO_DEBUG=False`;
- `DJANGO_SECRET_KEY` forte;
- domínio em `DJANGO_ALLOWED_HOSTS`;
- origem HTTPS em `DJANGO_CSRF_TRUSTED_ORIGINS`;
- PostgreSQL configurado;
- SMTP testado;
- `python manage.py migrate --noinput` executado;
- `python manage.py collectstatic --noinput` executado;
- `python manage.py check --deploy` sem alertas;
- superadmin criado ou redefinido;
- `/saude/` respondendo;
- primeiro curso testado do início ao certificado.
