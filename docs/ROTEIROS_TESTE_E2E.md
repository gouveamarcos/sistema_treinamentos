# Roteiros de Teste Ponta a Ponta

Este documento organiza a homologação completa da Academia Técnica Sem Parar.

Use os roteiros como checklist. Para cada caso, registre:

- **Status**: Aprovado, Reprovado ou Bloqueado;
- **Evidência**: print, observação ou número do certificado;
- **Responsável pelo teste**;
- **Data do teste**.

## 1. Perfis testados

- **Superadmin**: acesso total ao sistema e ao admin Django.
- **Responsável operacional**: gerencia empresas atribuídas, técnicos,
  liberações, relatórios e histórico operacional.
- **Editor de cursos**: gerencia produtos, cursos, etapas, questões e
  alternativas.
- **Técnico**: realiza cursos, avaliações e emite certificados.
- **Usuário público**: valida certificados sem login.

## 2. Ambiente de teste

Preencha antes de iniciar:

```text
Ambiente:
URL:
Data:
Versão/commit:
Banco:
Navegador:
Responsável pela homologação:
```

## 3. Massa mínima de teste

Crie ou confirme a existência dos dados abaixo.

### Empresas

```text
Empresa A: Cliente Teste A
Empresa B: Cliente Teste B
```

### Usuários administrativos

```text
Superadmin:
Usuário: admin
E-mail: admin.teste@empresa.com

Responsável operacional A:
Usuário: operacional.a@empresa.com
E-mail: operacional.a@empresa.com
Empresa: Cliente Teste A
Papel: Responsável operacional

Editor de cursos:
Usuário: editor.cursos@empresa.com
E-mail: editor.cursos@empresa.com
Empresa: Cliente Teste A
Papel: Editor de cursos
```

### Técnicos

```text
Técnico A1:
Nome: Técnico Teste A1
E-mail: tecnico.a1@empresa.com
Matrícula: TEC-A1
Empresa: Cliente Teste A

Técnico A2:
Nome: Técnico Teste A2
E-mail: tecnico.a2@empresa.com
Matrícula: TEC-A2
Empresa: Cliente Teste A

Técnico B1:
Nome: Técnico Teste B1
E-mail: tecnico.b1@empresa.com
Matrícula: TEC-B1
Empresa: Cliente Teste B
```

### Curso

```text
Produto: Produto Teste
Curso: Curso E2E Completo
Validade: 12 meses
Nota mínima: 70
```

Etapas recomendadas:

1. Texto: Introdução.
2. Vídeo: Videoaula com link YouTube embed.
3. Teste: 1 questão simples.
4. Prova final: 2 questões, uma alternativa correta em cada.

Use link no formato:

```text
https://www.youtube.com/embed/ID_DO_VIDEO
```

## 4. Checklist de sanidade inicial

| Caso | Perfil | Passos | Resultado esperado | Status |
| --- | --- | --- | --- | --- |
| S-01 | Público | Acessar `/saude/` | Retorna `status: ok` e `database: ok` |  |
| S-02 | Público | Acessar `/` sem login | Sistema exibe tela pública ou redireciona para login conforme regra atual |  |
| S-03 | Público | Acessar `/login/` | Tela de login abre sem erro |  |
| S-04 | Público | Acessar `/certificados/validar/` | Tela de validação pública abre sem login |  |

## 5. Roteiro do Superadmin

### SA-01 Login do superadmin

**Objetivo**: confirmar acesso total.

Passos:

1. Acesse `/login/`.
2. Entre com o usuário superadmin.
3. Acesse `/admin/`.
4. Volte para `/`.

Resultado esperado:

- login realizado;
- `/admin/` acessível;
- menu operacional e menu de catálogo visíveis;
- telas de empresas, técnicos, responsáveis, produtos, cursos, relatórios,
  histórico e liberações acessíveis.

### SA-02 Cadastro de empresa

Passos:

1. Acesse `/empresas/`.
2. Cadastre `Cliente Teste A`.
3. Cadastre `Cliente Teste B`.
4. Edite uma empresa e altere telefone ou responsável.
5. Inative e reative uma empresa.

Resultado esperado:

- empresas criadas;
- alteração salva;
- status muda corretamente;
- evento aparece no histórico.

### SA-03 Cadastro manual de técnico

Passos:

1. Acesse `/tecnicos/`.
2. Cadastre o Técnico A1.
3. Cadastre o Técnico B1.
4. Edite o Técnico A1.
5. Inative e reative o Técnico A1.

Resultado esperado:

- técnicos vinculados à empresa correta;
- edição salva;
- status muda corretamente;
- eventos aparecem no histórico.

### SA-04 Importação de técnicos por CSV

Passos:

1. Acesse `/tecnicos/`.
2. Importe CSV para `Cliente Teste A`:

```csv
nome,email,matricula,telefone,equipe,regiao,ativo
Técnico Teste A2,tecnico.a2@empresa.com,TEC-A2,11999999999,Campo,Sudeste,sim
```

3. Tente importar um CSV sem coluna obrigatória.
4. Tente importar um arquivo não CSV.

Resultado esperado:

- CSV válido cria ou atualiza técnicos;
- CSV inválido mostra erro;
- arquivo não CSV é rejeitado;
- nenhuma importação inválida grava dados parciais.

### SA-05 Cadastro de responsáveis

Passos:

1. Acesse `/responsaveis/`.
2. Cadastre responsável operacional para `Cliente Teste A`.
3. Cadastre editor de cursos.
4. Reenvie convite de um responsável.
5. Inative e reative um responsável.

Resultado esperado:

- usuários vinculados às empresas;
- papéis corretos;
- convite enviado ou registrado no backend configurado;
- status muda corretamente;
- histórico registra cadastro, convite e status.

### SA-06 Cadastro de produto e curso

Passos:

1. Acesse `/catalogo/produtos/`.
2. Crie `Produto Teste`.
3. Acesse `/catalogo/cursos/`.
4. Crie `Curso E2E Completo`.
5. Defina validade de 12 meses.
6. Defina nota mínima 70.
7. Edite descrição.
8. Inative e reative o curso.

Resultado esperado:

- produto criado;
- curso vinculado ao produto;
- campos salvos;
- status muda corretamente;
- eventos aparecem no histórico.

### SA-07 Construtor de conteúdo

Passos:

1. Abra o conteúdo do curso.
2. Crie etapa de texto.
3. Crie etapa de vídeo com link embed do YouTube.
4. Crie etapa de teste.
5. Crie etapa de prova final.
6. Adicione questões e alternativas.
7. Marque uma alternativa correta por questão.
8. Edite uma questão.
9. Exclua uma alternativa de teste, se necessário.

Resultado esperado:

- etapas aparecem na ordem correta;
- videoaula é renderizada no curso;
- questões aparecem em testes/provas;
- alternativa correta fica salva;
- alterações aparecem no histórico.

### SA-08 Liberação manual de curso

Passos:

1. Acesse `/liberacoes/lote/`.
2. Selecione `Cliente Teste A`.
3. Selecione `Curso E2E Completo`.
4. Libere para Técnico A1 e Técnico A2.
5. Marque como obrigatório.

Resultado esperado:

- curso fica liberado para os técnicos selecionados;
- duplicidades são evitadas;
- histórico registra liberação.

### SA-09 Importação de liberações por CSV

Passos:

1. Acesse `/liberacoes/lote/`.
2. Use a importação CSV:

```csv
matricula,email,obrigatorio
TEC-A1,,sim
,tecnico.a2@empresa.com,nao
```

3. Tente importar Técnico B1 selecionando `Cliente Teste A`.

Resultado esperado:

- técnicos da empresa correta são liberados;
- técnico de outra empresa é rejeitado;
- erros não geram gravação parcial indevida.

### SA-10 Relatórios

Passos:

1. Acesse `/relatorios/treinamentos/`.
2. Filtre por `Cliente Teste A`.
3. Filtre por situação `Pendente`.
4. Exporte CSV.

Resultado esperado:

- totais aparecem;
- risco por empresa e por curso aparece;
- filtro altera tabela e indicadores;
- CSV contém somente dados filtrados.

### SA-11 Histórico

Passos:

1. Acesse `/historico/`.
2. Filtre por empresa.
3. Filtre por ação.
4. Busque por nome de técnico, curso ou importação.

Resultado esperado:

- eventos administrativos aparecem;
- filtros funcionam;
- eventos de outra empresa só aparecem para superadmin ou conforme escopo
  autorizado.

### SA-12 Admin Django

Passos:

1. Acesse `/admin/`.
2. Consulte empresas, técnicos, cursos liberados, conclusões e eventos de
   auditoria.
3. Use filtros de vencimento em conclusões.
4. Use ações em lote de cursos liberados.

Resultado esperado:

- admin acessível;
- filtros funcionam;
- ações em lote alteram registros corretamente;
- dados continuam coerentes nas telas operacionais.

## 6. Roteiro do Responsável Operacional

### RO-01 Login e menu

Passos:

1. Entre com o responsável operacional.
2. Acesse a página inicial.

Resultado esperado:

- vê atalhos operacionais;
- não vê atalhos de produtos e cursos;
- consegue acessar empresas, técnicos, liberações, relatórios e histórico;
- não consegue acessar `/catalogo/produtos/` nem `/catalogo/cursos/`.

### RO-02 Escopo de empresa

Passos:

1. Acesse `/empresas/`.
2. Confirme que aparece apenas a empresa atribuída.
3. Tente acessar ou alterar dados de outra empresa por URL direta, se souber o
   ID.

Resultado esperado:

- vê somente empresas do próprio escopo;
- acesso direto a empresa fora do escopo é bloqueado ou retorna não encontrado.

### RO-03 Técnicos da própria empresa

Passos:

1. Acesse `/tecnicos/`.
2. Cadastre um técnico na empresa atribuída.
3. Edite esse técnico.
4. Importe técnicos por CSV na empresa atribuída.
5. Tente cadastrar ou importar para empresa fora do escopo.

Resultado esperado:

- operações na própria empresa funcionam;
- empresa fora do escopo não aparece ou é rejeitada;
- histórico registra ações.

### RO-04 Liberação de cursos

Passos:

1. Acesse `/liberacoes/lote/`.
2. Selecione a empresa atribuída.
3. Libere curso para um técnico.
4. Libere curso para todos os técnicos ativos.
5. Importe liberações por CSV.
6. Tente incluir técnico de outra empresa.

Resultado esperado:

- liberações funcionam para a própria empresa;
- técnico de outra empresa é rejeitado;
- duplicidades não são criadas.

### RO-05 Relatórios e exportação

Passos:

1. Acesse `/relatorios/treinamentos/`.
2. Confira indicadores.
3. Exporte CSV.
4. Tente filtrar por outra empresa.

Resultado esperado:

- vê apenas dados da própria empresa;
- CSV também contém apenas dados da própria empresa;
- filtro forçado para outra empresa não vaza dados.

### RO-06 Histórico operacional

Passos:

1. Acesse `/historico/`.
2. Filtre por ação.
3. Busque uma importação ou liberação feita pelo responsável.

Resultado esperado:

- histórico mostra eventos da empresa atribuída;
- não mostra eventos de empresas fora do escopo.

## 7. Roteiro do Editor de Cursos

### EC-01 Login e menu

Passos:

1. Entre com o editor de cursos.
2. Acesse a página inicial.

Resultado esperado:

- vê atalhos de catálogo;
- não vê atalhos operacionais como técnicos, liberações e relatórios;
- não consegue acessar `/tecnicos/`, `/liberacoes/lote/` ou
  `/relatorios/treinamentos/`.

### EC-02 Produtos

Passos:

1. Acesse `/catalogo/produtos/`.
2. Crie um produto.
3. Edite o produto.
4. Inative e reative o produto.

Resultado esperado:

- produto criado e alterado;
- status muda corretamente;
- histórico registra as ações de catálogo.

### EC-03 Cursos

Passos:

1. Acesse `/catalogo/cursos/`.
2. Crie um curso.
3. Edite validade e nota mínima.
4. Inative e reative o curso.

Resultado esperado:

- curso criado;
- alterações salvas;
- curso respeita status ativo/inativo.

### EC-04 Conteúdo do curso

Passos:

1. Abra o conteúdo do curso.
2. Crie etapa texto.
3. Crie etapa vídeo com link YouTube embed.
4. Crie etapa teste.
5. Crie etapa prova.
6. Cadastre questões e alternativas.
7. Edite etapa, questão e alternativa.

Resultado esperado:

- conteúdo salvo;
- etapas aparecem em ordem;
- vídeo renderiza no fluxo do técnico;
- questões aparecem nas etapas avaliativas;
- histórico registra alterações.

### EC-05 Bloqueios operacionais

Passos:

1. Tente acessar `/empresas/`.
2. Tente acessar `/tecnicos/`.
3. Tente acessar `/liberacoes/lote/`.
4. Tente acessar `/relatorios/treinamentos/`.
5. Tente acessar `/historico/`.

Resultado esperado:

- acessos operacionais são bloqueados.

## 8. Roteiro do Técnico

### TEC-01 Primeiro acesso

Passos:

1. Acesse `/primeiro-acesso/`.
2. Informe e-mail e matrícula cadastrados.
3. Crie senha.
4. Faça login.

Resultado esperado:

- usuário é criado ou vinculado;
- técnico entra no sistema;
- cursos liberados aparecem.

### TEC-02 Falha no primeiro acesso

Passos:

1. Tente primeiro acesso com matrícula errada.
2. Tente primeiro acesso com e-mail não cadastrado.

Resultado esperado:

- sistema exibe mensagem de erro;
- acesso não é criado indevidamente.

### TEC-03 Login e recuperação de senha

Passos:

1. Entre com senha correta.
2. Saia do sistema.
3. Use `/senha/esqueci/`.
4. Abra o link recebido no backend de e-mail configurado.
5. Defina nova senha.
6. Faça login novamente.

Resultado esperado:

- login funciona;
- recuperação envia link;
- nova senha permite acesso;
- senha antiga deixa de funcionar.

### TEC-04 Navegação no curso

Passos:

1. Acesse um curso liberado.
2. Tente abrir uma etapa futura antes de concluir a anterior.
3. Conclua a primeira etapa.
4. Avance para a segunda etapa.

Resultado esperado:

- etapas futuras ficam bloqueadas até conclusão das anteriores;
- progresso avança em ordem.

### TEC-05 Videoaula

Passos:

1. Abra uma etapa de vídeo.
2. Verifique se o player aparece.
3. Reproduza alguns segundos.
4. Conclua a etapa.

Resultado esperado:

- vídeo carrega;
- etapa pode ser concluída;
- próxima etapa é liberada.

### TEC-06 Teste intermediário

Passos:

1. Abra etapa de teste.
2. Responda a questão.
3. Envie respostas.

Resultado esperado:

- sistema aceita resposta;
- etapa é concluída conforme regra atual;
- próxima etapa é liberada.

### TEC-07 Prova final aprovada

Passos:

1. Abra a prova final.
2. Responda corretamente.
3. Envie respostas.

Resultado esperado:

- sistema calcula nota;
- curso é aprovado;
- conclusão é registrada;
- certificado é gerado.

### TEC-08 Prova final reprovada

Passos:

1. Use outro técnico ou reinicie massa de teste.
2. Responda prova final abaixo da nota mínima.
3. Envie respostas.

Resultado esperado:

- sistema informa reprovação;
- curso fica disponível para nova tentativa conforme regra configurada;
- certificado não é gerado.

### TEC-09 Certificado

Passos:

1. Conclua um curso.
2. Abra o certificado.
3. Confira dados.
4. Use impressão do navegador ou salvar como PDF.

Resultado esperado:

- certificado mostra técnico, empresa, curso, data e código;
- código tem formato `CERT-XXXXXXXX`;
- impressão é legível.

### TEC-10 Curso vencido ou reciclagem

Passos:

1. Use um curso com validade.
2. Simule ou cadastre conclusão vencida.
3. Acesse o curso como técnico.

Resultado esperado:

- sistema identifica vencimento;
- técnico consegue iniciar nova tentativa quando aplicável;
- relatório mostra situação vencida.

## 9. Roteiro do Usuário Público

### PUB-01 Validar certificado existente

Passos:

1. Acesse `/certificados/validar/`.
2. Informe um código real `CERT-XXXXXXXX`.

Resultado esperado:

- sistema mostra dados do certificado;
- situação de validade aparece corretamente.

### PUB-02 Validar certificado inexistente

Passos:

1. Acesse `/certificados/validar/`.
2. Informe `CERT-INEXISTE`.

Resultado esperado:

- sistema informa que o certificado não foi encontrado.

### PUB-03 Acesso público restrito

Passos:

1. Sem login, tente acessar `/tecnicos/`.
2. Sem login, tente acessar `/catalogo/cursos/`.
3. Sem login, tente acessar `/relatorios/treinamentos/`.

Resultado esperado:

- usuário é redirecionado para login;
- dados internos não aparecem.

## 10. Testes de segurança e permissão

| Caso | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| SEG-01 | Técnico tenta acessar `/admin/` | Acesso negado ou login sem permissão |  |
| SEG-02 | Técnico tenta acessar `/relatorios/treinamentos/` | Redireciona ou bloqueia |  |
| SEG-03 | Editor tenta acessar `/tecnicos/` | HTTP 403 ou bloqueio equivalente |  |
| SEG-04 | Operacional tenta acessar `/catalogo/cursos/` | HTTP 403 ou bloqueio equivalente |  |
| SEG-05 | Responsável A tenta ver dados da Empresa B | Dados não aparecem |  |
| SEG-06 | CSV acima do limite é enviado | Sistema rejeita arquivo |  |
| SEG-07 | Arquivo não CSV é enviado como importação | Sistema rejeita arquivo |  |
| SEG-08 | Logout é realizado | Sessão encerrada, páginas internas exigem login |  |

## 11. Testes de e-mail

| Caso | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| EMAIL-01 | Cadastrar responsável | Convite enviado |  |
| EMAIL-02 | Reenviar convite | Novo convite enviado |  |
| EMAIL-03 | Usar esqueci senha | Link temporário enviado |  |
| EMAIL-04 | Rodar lembrete de reciclagem | Técnicos com vencimento recebem aviso |  |

Comando de lembretes:

```powershell
.\venv\Scripts\python.exe manage.py enviar_lembretes_reciclagem
```

## 12. Testes de relatório e dados

| Caso | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| REL-01 | Curso pendente liberado | Relatório conta como pendente |  |
| REL-02 | Curso em andamento | Relatório conta como em andamento |  |
| REL-03 | Curso aprovado vigente | Relatório conta como em dia |  |
| REL-04 | Certificado vence em até 30 dias | Relatório conta como vence em 30 dias |  |
| REL-05 | Certificado vencido | Relatório conta como vencido |  |
| REL-06 | Certificado sem vencimento | Relatório conta como sem vencimento |  |
| REL-07 | Exportar CSV filtrado | CSV respeita filtros |  |

## 13. Testes de produção

Execute no ambiente publicado.

| Caso | Passos | Resultado esperado | Status |
| --- | --- | --- | --- |
| PROD-01 | Acessar domínio principal | Sistema abre em HTTPS |  |
| PROD-02 | Acessar `/saude/` | `status: ok`, `database: ok` |  |
| PROD-03 | Rodar `python manage.py check --deploy` | Sem alertas |  |
| PROD-04 | Rodar `python manage.py migrate --noinput` | Migrações aplicadas |  |
| PROD-05 | Rodar `python manage.py collectstatic --noinput` | Estáticos coletados |  |
| PROD-06 | Testar envio SMTP real | E-mail entregue |  |
| PROD-07 | Criar backup | Backup gerado e armazenado |  |

## 14. Modelo de registro de defeitos

Use este modelo para cada problema encontrado.

```text
ID:
Data:
Perfil:
Caso de teste:
Ambiente:
Passos executados:
Resultado esperado:
Resultado obtido:
Evidência:
Gravidade: Baixa / Média / Alta / Crítica
Status: Aberto / Corrigido / Reteste aprovado
Observações:
```

## 15. Critérios para aprovar a homologação

Considere a plataforma aprovada quando:

- todos os casos críticos de login, permissão, curso, prova e certificado
  estiverem aprovados;
- nenhum perfil visualizar dados fora do próprio escopo;
- importações inválidas forem rejeitadas;
- relatórios e CSVs baterem com os dados cadastrados;
- e-mails essenciais forem entregues no ambiente alvo;
- `/saude/` estiver respondendo;
- não houver defeitos críticos ou altos abertos.

## 16. Ordem recomendada de execução

1. Sanidade inicial.
2. Superadmin.
3. Editor de cursos.
4. Responsável operacional.
5. Técnico.
6. Usuário público.
7. Segurança e permissões.
8. E-mails.
9. Relatórios.
10. Produção.
