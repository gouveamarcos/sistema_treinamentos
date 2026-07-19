# Roteiro de Teste Ponta a Ponta

Este roteiro serve para testar a plataforma inteira, do começo ao fim, como uma pessoa comum usaria.

Use um teste por vez. Ao terminar cada item, marque:

```text
Status: Aprovado / Reprovado / Bloqueado
Observação:
Print ou evidência:
```

## Antes De Começar

1. Abra o terminal do projeto.
2. Ative o ambiente virtual, se ainda não estiver ativo.
3. Rode o servidor:

```powershell
python .\manage.py runserver
```

4. Abra o navegador em:

```text
http://127.0.0.1:8000/
```

5. Se aparecer uma tela de login, tudo bem.

## Dados De Teste

Durante os testes, use nomes fáceis de reconhecer:

```text
Empresa principal: Cliente Teste A
Empresa de comparação: Sem Parar
Produto da Cliente Teste A: Produto Teste Cliente A
Curso da Cliente Teste A: Curso Teste Cliente A
Técnico da Cliente Teste A: Técnico Teste A1
Responsável operacional: Responsável Operacional A
Editor de cursos: Editor Cursos A
```

## Teste 1: Verificar Se O Sistema Está No Ar

Perfil: qualquer pessoa, sem login.

Passos:

1. Acesse `http://127.0.0.1:8000/saude/`.

Resultado esperado:

- Deve aparecer algo parecido com:

```text
{"status": "ok", "database": "ok"}
```

## Teste 2: Entrar Como Superadmin

Perfil: superadmin.

Passos:

1. Acesse `http://127.0.0.1:8000/login/`.
2. Entre com o usuário administrador.
3. Depois do login, acesse `http://127.0.0.1:8000/`.

Resultado esperado:

- Deve abrir a página **Painel do superadmin**.
- Essa página deve mostrar um resumo geral da plataforma.
- Essa página deve listar as empresas.
- Não deve aparecer o menu operacional completo no topo.
- Deve existir o botão **Acessar painel da empresa** em cada empresa ativa.

## Teste 3: Acessar O Painel De Uma Empresa

Perfil: superadmin.

Passos:

1. Na página inicial do superadmin, encontre a empresa `Cliente Teste A`.
2. Clique em **Acessar painel da empresa**.

Resultado esperado:

- Deve abrir o painel da `Cliente Teste A`.
- O topo deve mostrar que você está operando a `Cliente Teste A`.
- Agora sim deve aparecer o menu operacional completo.
- O menu deve permitir acessar:
  - Empresas;
  - Técnicos;
  - Relatórios;
  - Histórico;
  - Liberar cursos;
  - Responsáveis;
  - Produtos;
  - Cursos.

## Teste 4: Voltar Para A Home Do Superadmin

Perfil: superadmin.

Passos:

1. Enquanto estiver no painel da empresa, acesse `http://127.0.0.1:8000/`.

Resultado esperado:

- Deve voltar para o **Painel do superadmin**.
- Não deve abrir automaticamente o painel da última empresa acessada.
- A lista de empresas deve aparecer novamente.

## Teste 5: Criar Ou Conferir A Empresa Cliente Teste A

Perfil: superadmin.

Passos:

1. Acesse o painel do superadmin.
2. Se a empresa `Cliente Teste A` não existir, clique no menu de empresas ou acesse `http://127.0.0.1:8000/empresas/`.
3. Cadastre a empresa:

```text
Nome: Cliente Teste A
Documento: 00.000.000/0001-00
Responsável: Contato Teste A
E-mail: contato.a@teste.com
Telefone: (11) 99999-0000
Ativa: marcado
```

Resultado esperado:

- A empresa aparece na lista.
- A empresa fica com status **Ativa**.
- Ao clicar em **Acessar painel da empresa**, abre o painel dela.

## Teste 6: Cadastrar Produto Da Empresa

Perfil: superadmin dentro do painel da `Cliente Teste A`.

Passos:

1. Primeiro entre no painel da `Cliente Teste A`.
2. Clique em **Produtos** no menu superior.
3. Cadastre:

```text
Nome: Produto Teste Cliente A
Descrição: Produto usado para teste de ponta a ponta.
Ativo: marcado
```

4. Clique em **Salvar produto**.

Resultado esperado:

- Deve aparecer mensagem de sucesso.
- O produto deve aparecer na tabela da tela.
- Esse produto pertence somente à `Cliente Teste A`.

## Teste 7: Cadastrar Curso Da Empresa

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
- O curso fica ligado ao produto da `Cliente Teste A`.
- Não deve existir campo para escolher várias empresas no curso.

## Teste 8: Criar Conteúdo Do Curso

Perfil: superadmin dentro do painel da `Cliente Teste A`.

Passos:

1. Na tabela de cursos, clique em **Conteúdo** no `Curso Teste Cliente A`.
2. Crie uma etapa de texto:

```text
Título: Introdução
Tipo: Conteúdo em texto
Ordem: 1
Conteúdo: Texto simples de introdução.
Ativo: marcado
```

3. Crie uma etapa de vídeo:

```text
Título: Videoaula
Tipo: Vídeo
Ordem: 2
Video URL: https://www.youtube.com/embed/ID_DO_VIDEO
Ativo: marcado
```

4. Crie uma etapa de prova:

```text
Título: Prova final
Tipo: Prova final
Ordem: 3
Ativo: marcado
```

5. Na prova, crie pelo menos uma questão.
6. Cadastre alternativas.
7. Marque uma alternativa como correta.

Resultado esperado:

- As etapas aparecem em ordem.
- A etapa de vídeo salva o link.
- A prova mostra questão e alternativas.
- Existe uma alternativa correta.

## Teste 9: Cadastrar Técnico Da Empresa

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

- O técnico aparece na lista.
- Ele pertence à `Cliente Teste A`.
- Deve aparecer mensagem de sucesso.

## Teste 10: Criar Responsável Operacional

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

- O responsável aparece na tabela.
- O acesso aparece como **Convite pendente**, se ele ainda não definiu senha.
- Deve aparecer mensagem de sucesso.
- O terminal pode mostrar o e-mail de convite, se o envio estiver configurado para console.

## Teste 11: Testar Convite E Primeiro Acesso Do Responsável

Perfil: responsável operacional.

Passos:

1. Copie o link de convite exibido no terminal ou recebido por e-mail.
2. Abra em janela anônima ou outro navegador.
3. Defina a senha.
4. Faça login com o e-mail do responsável.

Resultado esperado:

- O responsável consegue criar senha.
- Depois consegue fazer login.
- Ele entra no painel da empresa dele.
- Ele não deve ver cursos/produtos de outras empresas.

## Teste 12: Conferir Menu Do Responsável Operacional

Perfil: responsável operacional da `Cliente Teste A`.

Passos:

1. Faça login como responsável operacional.
2. Observe a página inicial e o menu.

Resultado esperado:

- Deve conseguir acessar:
  - Técnicos;
  - Relatórios;
  - Histórico;
  - Liberar cursos;
  - Responsáveis, se permitido pelo papel atual.
- Não deve conseguir acessar:
  - Produtos;
  - Cursos.

## Teste 13: Liberar Curso Para Técnico

Perfil: superadmin ou responsável operacional dentro da `Cliente Teste A`.

Passos:

1. Clique em **Liberar cursos**.
2. Em empresa, escolha `Cliente Teste A`.
3. Em curso, escolha `Curso Teste Cliente A`.
4. Selecione o técnico `Técnico Teste A1`.
5. Marque **Curso obrigatório**.
6. Clique para liberar.

Resultado esperado:

- Deve aparecer mensagem de sucesso.
- A liberação deve contar como criada.
- O técnico passa a enxergar o curso ao entrar na plataforma.

## Teste 14: Garantir Que Cursos De Outra Empresa Não Aparecem

Perfil: responsável operacional da `Cliente Teste A`.

Passos:

1. Acesse **Liberar cursos**.
2. Observe a lista de cursos.

Resultado esperado:

- Deve aparecer somente curso ligado à `Cliente Teste A`.
- Cursos da `Sem Parar` não devem aparecer.
- Produtos da `Sem Parar` não devem aparecer.

## Teste 15: Criar Acesso Do Técnico

Perfil: técnico.

Passos:

1. Saia do sistema.
2. Acesse `http://127.0.0.1:8000/primeiro-acesso/`.
3. Informe:

```text
E-mail: tecnico.a1@teste.com
Matrícula: TEC-A1
Senha: escolha uma senha segura
```

4. Salve.
5. Faça login como técnico.

Resultado esperado:

- O técnico consegue criar acesso.
- Ao entrar, ele vê o produto/curso liberado.

## Teste 16: Técnico Inicia O Curso

Perfil: técnico.

Passos:

1. Faça login como `Técnico Teste A1`.
2. Clique no produto liberado.
3. Clique no curso.
4. Abra a primeira etapa.

Resultado esperado:

- O curso abre.
- A primeira etapa aparece.
- Etapas futuras não devem poder ser feitas fora de ordem.

## Teste 17: Técnico Conclui Etapa De Texto

Perfil: técnico.

Passos:

1. Leia a etapa de texto.
2. Clique para concluir ou avançar.

Resultado esperado:

- A etapa fica concluída.
- A próxima etapa fica disponível.

## Teste 18: Técnico Assiste Videoaula

Perfil: técnico.

Passos:

1. Abra a etapa de vídeo.
2. Veja se o player aparece.
3. Reproduza alguns segundos.
4. Conclua a etapa.

Resultado esperado:

- O vídeo aparece na tela.
- A etapa pode ser concluída.
- A prova final fica disponível depois disso.

## Teste 19: Técnico Faz A Prova E É Aprovado

Perfil: técnico.

Passos:

1. Abra a prova final.
2. Responda marcando a alternativa correta.
3. Envie a prova.

Resultado esperado:

- O sistema calcula a nota.
- Como a nota mínima é 70, o técnico deve ser aprovado se respondeu corretamente.
- O curso fica concluído.
- O certificado é gerado.

## Teste 20: Conferir Certificado

Perfil: técnico.

Passos:

1. Após concluir o curso, abra o certificado.
2. Confira os dados:
   - nome do técnico;
   - empresa;
   - curso;
   - data;
   - código do certificado.
3. Anote o código.

Resultado esperado:

- O certificado aparece corretamente.
- O código deve começar com `CERT-`.
- A impressão ou visualização deve estar legível.

## Teste 21: Validar Certificado Sem Login

Perfil: usuário público.

Passos:

1. Saia do sistema.
2. Acesse `http://127.0.0.1:8000/certificados/validar/`.
3. Digite o código do certificado.
4. Clique em validar.

Resultado esperado:

- O sistema mostra que o certificado existe.
- Deve aparecer o nome do técnico, empresa, curso e situação.

## Teste 22: Validar Certificado Inexistente

Perfil: usuário público.

Passos:

1. Acesse `http://127.0.0.1:8000/certificados/validar/`.
2. Digite:

```text
CERT-INEXISTE
```

3. Clique em validar.

Resultado esperado:

- O sistema informa que o certificado não foi encontrado.

## Teste 23: Relatório Da Empresa

Perfil: superadmin ou responsável operacional dentro da `Cliente Teste A`.

Passos:

1. Entre no painel da `Cliente Teste A`.
2. Clique em **Relatórios**.
3. Confira os números.
4. Exporte o CSV.

Resultado esperado:

- O relatório mostra os treinamentos da `Cliente Teste A`.
- O técnico aprovado aparece como em dia, se concluiu o curso.
- O CSV deve baixar ou abrir com os dados filtrados da empresa.
- Dados da `Sem Parar` não devem aparecer quando estiver operando `Cliente Teste A`.

## Teste 24: Histórico Da Empresa

Perfil: superadmin ou responsável operacional dentro da `Cliente Teste A`.

Passos:

1. Clique em **Histórico**.
2. Procure eventos de:
   - criação de produto;
   - criação de curso;
   - criação de técnico;
   - liberação de curso;
   - conclusão/certificado, se aparecer no histórico atual.

Resultado esperado:

- O histórico mostra ações realizadas na `Cliente Teste A`.
- Não deve misturar ações de outra empresa no painel dessa empresa.

## Teste 25: Recuperação De Senha

Perfil: responsável ou técnico.

Passos:

1. Saia do sistema.
2. Acesse `http://127.0.0.1:8000/senha/esqueci/`.
3. Informe o e-mail cadastrado.
4. Clique para enviar link.
5. Pegue o link no e-mail ou no terminal.
6. Abra o link.
7. Defina uma nova senha.
8. Faça login com a nova senha.

Resultado esperado:

- O link permite redefinir a senha.
- A nova senha funciona.
- A senha antiga não deve mais funcionar.

## Teste 26: Bloqueios De Permissão

Execute estes testes com cuidado. O objetivo é confirmar que um perfil não acessa o que não deveria.

### Responsável operacional tentando acessar catálogo

Passos:

1. Faça login como responsável operacional.
2. Tente acessar:

```text
http://127.0.0.1:8000/catalogo/produtos/
http://127.0.0.1:8000/catalogo/cursos/
```

Resultado esperado:

- O sistema deve bloquear o acesso.

### Técnico tentando acessar telas administrativas

Passos:

1. Faça login como técnico.
2. Tente acessar:

```text
http://127.0.0.1:8000/tecnicos/
http://127.0.0.1:8000/liberacoes/lote/
http://127.0.0.1:8000/relatorios/treinamentos/
```

Resultado esperado:

- O sistema deve bloquear ou redirecionar para login.
- Dados administrativos não devem aparecer.

### Usuário sem login tentando acessar telas internas

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

## Teste 27: Importar Técnicos Por CSV

Perfil: superadmin dentro da `Cliente Teste A`.

Passos:

1. Entre no painel da `Cliente Teste A`.
2. Clique em **Técnicos**.
3. Use a área de importação CSV.
4. Importe um arquivo com este conteúdo:

```csv
nome,email,matricula,telefone,equipe,regiao,ativo
Técnico Teste A2,tecnico.a2@teste.com,TEC-A2,11999999999,Campo,Sudeste,sim
```

Resultado esperado:

- O técnico `Técnico Teste A2` aparece na lista.
- Ele pertence à `Cliente Teste A`.
- Deve aparecer mensagem de sucesso.

## Teste 28: Importar Liberações Por CSV

Perfil: superadmin dentro da `Cliente Teste A`.

Passos:

1. Entre no painel da `Cliente Teste A`.
2. Clique em **Liberar cursos**.
3. Use a importação de liberações.
4. Importe:

```csv
matricula,email,obrigatorio
TEC-A1,,sim
TEC-A2,,sim
```

Resultado esperado:

- Os técnicos informados recebem a liberação.
- Se algum já tinha a liberação, o sistema não cria duplicidade.
- Deve aparecer uma mensagem informando criados, reativados ou existentes.

## Teste 29: Testar Empresa Sem Parar Separadamente

Perfil: superadmin.

Passos:

1. Acesse `http://127.0.0.1:8000/`.
2. Clique em **Acessar painel da empresa** na empresa `Sem Parar`.
3. Clique em **Produtos**.
4. Clique em **Cursos**.

Resultado esperado:

- Produtos e cursos da `Sem Parar` aparecem dentro da `Sem Parar`.
- Esses produtos/cursos não aparecem quando você opera `Cliente Teste A`.

## Teste 30: Encerramento Da Sessão

Perfil: qualquer usuário logado.

Passos:

1. Clique em **Sair**.
2. Tente voltar para uma tela interna usando o botão voltar do navegador.

Resultado esperado:

- O usuário sai do sistema.
- Telas internas devem pedir login novamente.

## Modelo Para Registrar Problemas

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

## Critério Para Considerar O Teste Aprovado

A plataforma pode ser considerada aprovada quando:

- superadmin tem uma home própria;
- cada empresa tem seu próprio painel;
- produtos e cursos ficam dentro da empresa correta;
- responsável operacional não vê catálogo de outra empresa;
- técnico consegue acessar, fazer curso, prova e certificado;
- certificado pode ser validado sem login;
- relatórios e histórico respeitam a empresa em operação;
- perfis sem permissão são bloqueados;
- e-mails essenciais funcionam no ambiente configurado.

