# Roteiro De Teste Ponta A Ponta

Este roteiro foi escrito para uma pessoa que vai testar a plataforma pela primeira vez, em uma máquina nova, sem conhecer o projeto.

A ideia é seguir na ordem. Não pule etapas, porque os testes finais dependem dos cadastros feitos no começo.

Para cada teste, anote:

```text
Status: Aprovado / Reprovado / Bloqueado
Observação:
Print ou evidência:
```

## 1. Preparar O Projeto Pela Primeira Vez

### Teste 1.1: Abrir A Pasta Do Projeto

Perfil: pessoa responsável pelo teste.

Passos:

1. Abra o **PowerShell**.
2. Entre na pasta onde o projeto foi instalado.

Exemplo:

```powershell
D:
cd .\Projetos\sistema_treinamentos\
```

Resultado esperado:

- O terminal deve ficar dentro da pasta do projeto.
- A pasta deve ter arquivos como `manage.py`, `requirements.txt`, `core` e `treinamentos`.

### Teste 1.2: Criar O Ambiente Virtual

Faça este passo somente se ainda não existir a pasta `venv`.

Passos:

1. No PowerShell, rode:

```powershell
python -m venv venv
```

2. Ative o ambiente virtual:

```powershell
.\venv\Scripts\activate
```

Resultado esperado:

- O terminal deve mostrar `(venv)` no começo da linha.

### Teste 1.3: Instalar As Dependências

Passos:

1. Com o ambiente virtual ativo, rode:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Resultado esperado:

- O comando termina sem erro.
- O Django e as demais bibliotecas são instalados.

### Teste 1.4: Preparar O Banco De Dados

Passos:

1. Rode:

```powershell
python .\manage.py migrate
```

Resultado esperado:

- O sistema cria ou atualiza o banco de dados.
- Deve aparecer uma lista de migrações aplicadas ou a mensagem de que não há migrações pendentes.

### Teste 1.5: Criar O Primeiro Administrador

Passos:

1. Rode:

```powershell
python .\manage.py redefinir_admin --username admin --email admin@teste.com
```

2. Digite uma senha segura quando o terminal pedir.
3. Confirme a senha.

Resultado esperado:

- Deve aparecer a mensagem:

```text
Administrador 'admin' criado com sucesso.
```

ou:

```text
Administrador 'admin' redefinido com sucesso.
```

Guarde estes dados:

```text
Usuário: admin
Senha: a senha que você escolheu
```

### Teste 1.6: Iniciar O Sistema

Passos:

1. Rode:

```powershell
python .\manage.py runserver
```

2. Deixe esse terminal aberto.
3. Abra o navegador em:

```text
http://127.0.0.1:8000/
```

Resultado esperado:

- O navegador deve abrir a plataforma.
- Se aparecer tela de login, está correto.

### Teste 1.7: Conferir Se O Sistema Está Saudável

Passos:

1. No navegador, acesse:

```text
http://127.0.0.1:8000/saude/
```

Resultado esperado:

- Deve aparecer algo parecido com:

```text
{"status": "ok", "database": "ok"}
```

## 2. Entrar Como Superadmin

### Teste 2.1: Login Do Administrador

Perfil: superadmin.

Passos:

1. Acesse:

```text
http://127.0.0.1:8000/login/
```

2. Entre com:

```text
Usuário: admin
Senha: senha escolhida no Teste 1.5
```

3. Depois do login, acesse:

```text
http://127.0.0.1:8000/
```

Resultado esperado:

- Deve aparecer a página **Painel do superadmin**.
- Essa página deve mostrar um resumo geral.
- Ainda não deve aparecer o menu operacional completo no topo.
- Deve existir o botão **Gerenciar empresas**.

## 3. Criar A Primeira Empresa

### Teste 3.1: Cadastrar Cliente Teste A

Perfil: superadmin.

Passos:

1. No **Painel do superadmin**, clique em **Gerenciar empresas**.

2. Cadastre:

```text
Nome: Cliente Teste A
Documento: 00.000.000/0001-00
Responsável: Contato Teste A
E-mail: contato.a@teste.com
Telefone: (11) 99999-0000
Ativa: marcado
```

3. Clique em **Criar empresa**.

Resultado esperado:

- Deve aparecer mensagem de sucesso.
- A empresa `Cliente Teste A` deve aparecer na tabela.
- O status deve ser **Ativa**.

### Teste 3.2: Cadastrar Empresa Sem Parar

Este teste ajuda a confirmar que uma empresa não vê dados da outra.

Passos:

1. Na mesma tela de empresas, cadastre:

```text
Nome: Sem Parar
Documento: deixe vazio ou preencha um documento de teste
Responsável: Administrador
E-mail: admin@semparar.test
Telefone: deixe vazio
Ativa: marcado
```

2. Clique em **Criar empresa**.

Resultado esperado:

- A empresa `Sem Parar` deve aparecer na tabela.
- Ela deve ficar ativa.

## 4. Acessar O Painel Da Empresa

### Teste 4.1: Entrar No Painel Da Cliente Teste A

Perfil: superadmin.

Passos:

1. Acesse:

```text
http://127.0.0.1:8000/
```

2. Encontre `Cliente Teste A`.
3. Clique em **Acessar painel da empresa**.

Resultado esperado:

- Deve abrir o painel da `Cliente Teste A`.
- O topo deve mostrar que você está operando a `Cliente Teste A`.
- Agora deve aparecer o menu completo da empresa:
  - Empresas;
  - Técnicos;
  - Relatórios;
  - Histórico;
  - Liberar cursos;
  - Responsáveis;
  - Produtos;
  - Cursos.

### Teste 4.2: Voltar Para A Home Do Superadmin

Passos:

1. Enquanto estiver no painel da empresa, acesse:

```text
http://127.0.0.1:8000/
```

Resultado esperado:

- Deve voltar para o **Painel do superadmin**.
- A lista de empresas deve aparecer.
- O menu operacional completo não deve aparecer nessa home.

## 5. Criar Produto E Curso Da Cliente Teste A

### Teste 5.1: Criar Produto

Perfil: superadmin dentro do painel da `Cliente Teste A`.

Passos:

1. Entre no painel da `Cliente Teste A`.
2. Clique em **Produtos**.
3. Cadastre:

```text
Nome: Produto Teste Cliente A
Descrição: Produto usado para teste de ponta a ponta.
Ativo: marcado
```

4. Clique em **Salvar produto**.

Resultado esperado:

- Deve aparecer mensagem de sucesso.
- O produto deve aparecer na tabela.
- Esse produto pertence à `Cliente Teste A`.

### Teste 5.2: Criar Curso

Perfil: superadmin dentro do painel da `Cliente Teste A`.

Passos:

1. Clique em **Cursos**.
2. Cadastre:

```text
Produto: Produto Teste Cliente A
Nome: Curso Teste Cliente A
Descrição: Curso usado para teste de ponta a ponta.
Validade meses: 12
Nota mínima: 70
Link NotebookLM: deixe vazio
Ativo: marcado
```

3. Clique em **Salvar curso**.

Resultado esperado:

- Deve aparecer mensagem de sucesso.
- O curso aparece na tabela.
- O curso está ligado ao produto da `Cliente Teste A`.
- Não deve existir campo para escolher várias empresas no curso.

## 6. Criar Conteúdo Do Curso

### Teste 6.1: Abrir O Construtor Do Curso

Perfil: superadmin dentro do painel da `Cliente Teste A`.

Passos:

1. Clique em **Cursos**.
2. Na linha `Curso Teste Cliente A`, clique em **Conteúdo**.

Resultado esperado:

- Deve abrir a tela de conteúdo do curso.
- A tela deve permitir criar etapas.

### Teste 6.2: Criar Etapa De Texto

Passos:

1. Cadastre uma etapa:

```text
Título: Introdução
Descrição: Primeira etapa do curso.
Tipo: Conteúdo em texto
Ordem: 1
Conteúdo: Texto simples de introdução ao curso.
Ativo: marcado
```

2. Salve.

Resultado esperado:

- A etapa aparece na lista.
- A ordem exibida é `1`.

### Teste 6.3: Criar Etapa De Vídeo

Passos:

1. Cadastre uma etapa:

```text
Título: Videoaula
Descrição: Aula em vídeo.
Tipo: Vídeo
Ordem: 2
Video URL: https://www.youtube.com/embed/ID_DO_VIDEO
Ativo: marcado
```

2. Salve.

Resultado esperado:

- A etapa aparece na lista.
- A ordem exibida é `2`.

Observação:

- O link precisa estar no formato `https://www.youtube.com/embed/...`.
- Link comum do YouTube pode não funcionar como vídeo incorporado.

### Teste 6.4: Criar Prova Final

Passos:

1. Cadastre uma etapa:

```text
Título: Prova final
Descrição: Avaliação final do curso.
Tipo: Prova final
Ordem: 3
Ativo: marcado
```

2. Salve.

Resultado esperado:

- A prova aparece na lista.
- A ordem exibida é `3`.

### Teste 6.5: Criar Questão E Alternativas

Passos:

1. Na etapa **Prova final**, crie uma questão:

```text
Enunciado: Qual é a resposta correta deste teste?
Ordem: 1
```

2. Crie pelo menos três alternativas:

```text
Alternativa 1: Resposta errada
Alternativa 2: Resposta correta
Alternativa 3: Outra resposta errada
```

3. Marque somente a alternativa `Resposta correta` como correta.

Resultado esperado:

- A questão aparece dentro da prova.
- As alternativas aparecem.
- Apenas uma alternativa fica marcada como correta.

## 7. Cadastrar Técnico

### Teste 7.1: Criar Técnico Da Cliente Teste A

Perfil: superadmin dentro do painel da `Cliente Teste A`.

Passos:

1. Clique em **Técnicos**.
2. Cadastre:

```text
Empresa: Cliente Teste A
Nome: Técnico Teste A1
E-mail: tecnico.a1@teste.com
Matrícula: TEC-A1
Telefone: (11) 99999-1111
Equipe: Campo
Região: Sudeste
Ativo: marcado
```

3. Clique em **Salvar técnico**.

Resultado esperado:

- Deve aparecer mensagem de sucesso.
- O técnico aparece na lista.
- Ele pertence à `Cliente Teste A`.

## 8. Cadastrar Responsável Operacional

### Teste 8.1: Criar Responsável Da Cliente Teste A

Perfil: superadmin dentro do painel da `Cliente Teste A`.

Passos:

1. Clique em **Responsáveis**.
2. Cadastre:

```text
Empresa: Cliente Teste A
Nome: Responsável Operacional A
E-mail: operacional.a@teste.com
Papel: Responsável operacional
Responsável ativo: marcado
```

3. Clique em **Salvar responsável**.

Resultado esperado:

- Deve aparecer mensagem de sucesso.
- O responsável aparece na tabela.
- O acesso pode aparecer como **Convite pendente**.
- O terminal pode mostrar o e-mail de convite, caso o sistema esteja configurado para mostrar e-mails no console.

### Teste 8.2: Criar Senha Do Responsável

Perfil: responsável operacional.

Passos:

1. Copie o link de convite exibido no terminal ou recebido por e-mail.
2. Abra o link em janela anônima ou em outro navegador.
3. Defina uma senha.
4. Faça login usando:

```text
Usuário/e-mail: operacional.a@teste.com
Senha: senha criada no convite
```

Resultado esperado:

- O responsável consegue criar a senha.
- Depois consegue entrar no sistema.
- Ele deve operar a `Cliente Teste A`.

## 9. Testar Permissões Do Responsável

### Teste 9.1: Conferir Menu Do Responsável

Perfil: responsável operacional.

Passos:

1. Faça login como `operacional.a@teste.com`.
2. Observe a página inicial e o menu.

Resultado esperado:

- O responsável deve conseguir acessar telas operacionais da empresa.
- Ele não deve ter acesso ao catálogo de produtos e cursos.

### Teste 9.2: Tentar Acessar Catálogo Sem Permissão

Passos:

1. Ainda logado como responsável, tente abrir:

```text
http://127.0.0.1:8000/catalogo/produtos/
http://127.0.0.1:8000/catalogo/cursos/
```

Resultado esperado:

- O sistema deve bloquear o acesso.
- Dados de produtos e cursos não devem aparecer.

## 10. Liberar Curso Para Técnico

### Teste 10.1: Fazer Liberação Manual

Perfil: superadmin ou responsável operacional dentro da `Cliente Teste A`.

Passos:

1. Entre no painel da `Cliente Teste A`.
2. Clique em **Liberar cursos**.
3. Selecione:

```text
Empresa: Cliente Teste A
Curso: Curso Teste Cliente A
Técnico: Técnico Teste A1
Curso obrigatório: marcado
```

4. Clique para liberar.

Resultado esperado:

- Deve aparecer mensagem de sucesso.
- A liberação deve ser criada.
- Se repetir o mesmo processo, o sistema não deve criar duplicidade.

### Teste 10.2: Conferir Que Curso De Outra Empresa Não Aparece

Perfil: responsável operacional da `Cliente Teste A`.

Passos:

1. Acesse **Liberar cursos**.
2. Veja a lista de cursos disponíveis.

Resultado esperado:

- Deve aparecer somente curso da `Cliente Teste A`.
- Cursos da `Sem Parar` não devem aparecer.
- Produtos da `Sem Parar` não devem aparecer.

## 11. Criar Acesso Do Técnico

### Teste 11.1: Primeiro Acesso Do Técnico

Perfil: técnico.

Passos:

1. Saia do sistema.
2. Acesse:

```text
http://127.0.0.1:8000/primeiro-acesso/
```

3. Informe:

```text
E-mail: tecnico.a1@teste.com
Matrícula: TEC-A1
Senha: escolha uma senha segura
```

4. Salve.
5. Faça login como técnico.

Resultado esperado:

- O técnico consegue criar o acesso.
- Ao entrar, ele vê o produto/curso liberado.

## 12. Técnico Faz O Curso

### Teste 12.1: Abrir O Curso

Perfil: técnico.

Passos:

1. Faça login como `tecnico.a1@teste.com`.
2. Clique no produto liberado.
3. Clique no curso.
4. Abra a primeira etapa.

Resultado esperado:

- O curso abre.
- A primeira etapa aparece.
- Etapas futuras ficam bloqueadas até a conclusão das anteriores.

### Teste 12.2: Concluir Etapa De Texto

Passos:

1. Leia a etapa de texto.
2. Clique para concluir ou avançar.

Resultado esperado:

- A etapa fica concluída.
- A próxima etapa fica disponível.

### Teste 12.3: Assistir Videoaula

Passos:

1. Abra a etapa de vídeo.
2. Veja se o player aparece.
3. Reproduza alguns segundos.
4. Conclua a etapa.

Resultado esperado:

- O vídeo aparece na tela.
- A etapa pode ser concluída.
- A prova final fica disponível.

### Teste 12.4: Fazer A Prova Final

Passos:

1. Abra a prova final.
2. Marque a alternativa correta.
3. Envie a prova.

Resultado esperado:

- O sistema calcula a nota.
- O técnico é aprovado.
- O curso fica concluído.
- O certificado é gerado.

## 13. Certificado

### Teste 13.1: Conferir Certificado

Perfil: técnico.

Passos:

1. Após concluir o curso, abra o certificado.
2. Confira:
   - nome do técnico;
   - empresa;
   - curso;
   - data;
   - código do certificado.
3. Anote o código do certificado.

Resultado esperado:

- O certificado aparece corretamente.
- O código começa com `CERT-`.
- A tela de impressão é legível.

### Teste 13.2: Validar Certificado Sem Login

Perfil: público, sem login.

Passos:

1. Saia do sistema.
2. Acesse:

```text
http://127.0.0.1:8000/certificados/validar/
```

3. Digite o código do certificado.
4. Clique em validar.

Resultado esperado:

- O sistema mostra que o certificado existe.
- Deve aparecer o técnico, empresa, curso e situação do certificado.

### Teste 13.3: Validar Código Inexistente

Passos:

1. Na tela de validação, digite:

```text
CERT-INEXISTE
```

2. Clique em validar.

Resultado esperado:

- O sistema informa que o certificado não foi encontrado.

## 14. Relatórios E Histórico

### Teste 14.1: Conferir Relatório Da Empresa

Perfil: superadmin ou responsável dentro da `Cliente Teste A`.

Passos:

1. Entre no painel da `Cliente Teste A`.
2. Clique em **Relatórios**.
3. Confira os números.
4. Exporte o CSV.

Resultado esperado:

- O relatório mostra dados da `Cliente Teste A`.
- O técnico aprovado aparece como em dia.
- O CSV deve respeitar a empresa em operação.

### Teste 14.2: Conferir Histórico

Perfil: superadmin ou responsável dentro da `Cliente Teste A`.

Passos:

1. Clique em **Histórico**.
2. Procure eventos de:
   - criação de empresa;
   - criação de produto;
   - criação de curso;
   - criação de técnico;
   - liberação de curso.

Resultado esperado:

- O histórico mostra ações da `Cliente Teste A`.
- Não deve misturar ações de outra empresa quando você estiver operando `Cliente Teste A`.

## 15. Recuperação De Senha

### Teste 15.1: Redefinir Senha De Um Usuário

Perfil: responsável ou técnico.

Passos:

1. Saia do sistema.
2. Acesse:

```text
http://127.0.0.1:8000/senha/esqueci/
```

3. Informe um e-mail cadastrado.
4. Clique para enviar o link.
5. Pegue o link no e-mail ou no terminal.
6. Abra o link.
7. Defina uma nova senha.
8. Faça login com a nova senha.

Resultado esperado:

- O link permite redefinir a senha.
- A nova senha funciona.
- A senha antiga não deve mais funcionar.

## 16. Importações Por CSV

### Teste 16.1: Importar Técnicos

Perfil: superadmin dentro da `Cliente Teste A`.

Passos:

1. Entre no painel da `Cliente Teste A`.
2. Clique em **Técnicos**.
3. Use a importação CSV.
4. Crie um arquivo `.csv` com este conteúdo:

```csv
nome,email,matricula,telefone,equipe,regiao,ativo
Técnico Teste A2,tecnico.a2@teste.com,TEC-A2,11999999999,Campo,Sudeste,sim
```

5. Importe o arquivo.

Resultado esperado:

- O técnico `Técnico Teste A2` aparece na lista.
- Ele pertence à `Cliente Teste A`.

### Teste 16.2: Importar Liberações

Perfil: superadmin dentro da `Cliente Teste A`.

Passos:

1. Clique em **Liberar cursos**.
2. Use a importação de liberações.
3. Crie um arquivo `.csv` com:

```csv
matricula,email,obrigatorio
TEC-A1,,sim
TEC-A2,,sim
```

4. Importe o arquivo.

Resultado esperado:

- Os técnicos recebem a liberação.
- O sistema não cria duplicidade se a liberação já existir.
- Deve aparecer uma mensagem informando criados, reativados ou existentes.

## 17. Testar Separação Entre Empresas

### Teste 17.1: Criar Produto E Curso Na Sem Parar

Perfil: superadmin.

Passos:

1. Acesse:

```text
http://127.0.0.1:8000/
```

2. Clique em **Acessar painel da empresa** na empresa `Sem Parar`.
3. Clique em **Produtos**.
4. Crie:

```text
Nome: Produto Sem Parar
Descrição: Produto exclusivo da Sem Parar.
Ativo: marcado
```

5. Clique em **Cursos**.
6. Crie:

```text
Produto: Produto Sem Parar
Nome: Curso Sem Parar
Descrição: Curso exclusivo da Sem Parar.
Validade meses: 12
Nota mínima: 70
Ativo: marcado
```

Resultado esperado:

- Produto e curso aparecem dentro da `Sem Parar`.

### Teste 17.2: Confirmar Que Cliente Teste A Não Vê Curso Da Sem Parar

Perfil: superadmin ou responsável dentro da `Cliente Teste A`.

Passos:

1. Entre no painel da `Cliente Teste A`.
2. Clique em **Liberar cursos**.
3. Abra a lista de cursos.

Resultado esperado:

- `Curso Sem Parar` não aparece.
- Deve aparecer apenas curso da `Cliente Teste A`.

## 18. Bloqueios De Segurança

### Teste 18.1: Usuário Sem Login

Passos:

1. Saia do sistema.
2. Tente acessar:

```text
http://127.0.0.1:8000/tecnicos/
http://127.0.0.1:8000/catalogo/cursos/
http://127.0.0.1:8000/relatorios/treinamentos/
```

Resultado esperado:

- O sistema deve pedir login.
- Dados internos não devem aparecer.

### Teste 18.2: Técnico Tentando Acessar Administração

Perfil: técnico.

Passos:

1. Faça login como técnico.
2. Tente acessar:

```text
http://127.0.0.1:8000/tecnicos/
http://127.0.0.1:8000/liberacoes/lote/
http://127.0.0.1:8000/admin/
```

Resultado esperado:

- O sistema deve bloquear ou pedir login administrativo.
- Dados administrativos não devem aparecer.

## 19. Encerrar Sessão

### Teste 19.1: Logout

Perfil: qualquer usuário logado.

Passos:

1. Clique em **Sair**.
2. Tente voltar para uma tela interna pelo botão voltar do navegador.

Resultado esperado:

- O usuário sai do sistema.
- Telas internas devem pedir login novamente.

## 20. Modelo Para Registrar Problemas

Use este modelo sempre que algo não funcionar:

```text
Problema:
Quem estava logado:
Tela acessada:
O que eu cliquei/digitei:
O que eu esperava:
O que aconteceu:
Print:
Gravidade: baixa / média / alta / crítica
```

## 21. Critério Para Aprovar O Teste

Considere o teste aprovado quando:

- o projeto inicia em uma máquina nova;
- o banco é criado com `migrate`;
- o superadmin consegue entrar;
- o superadmin tem uma home própria;
- cada empresa tem seu próprio painel;
- produtos e cursos ficam dentro da empresa correta;
- responsável operacional não vê catálogo de outra empresa;
- técnico consegue criar acesso, fazer curso, prova e certificado;
- certificado pode ser validado sem login;
- relatórios e histórico respeitam a empresa em operação;
- perfis sem permissão são bloqueados;
- recuperação de senha funciona no ambiente configurado.
