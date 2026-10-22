# Instalação da Academia Técnica — comece aqui

Edição: 22/10/2026 · Para: equipe que vai instalar a plataforma num **Windows Server**.

## O que você vai montar

Tudo fica num único servidor Windows. Os usuários só acessam o site pelo navegador; ninguém instala nada no próprio computador.

```text
Navegador do usuário
      |  https://treinamentos.suaempresa.com.br  (porta 443)
      v
Caddy ............ recebe o acesso, cuida do HTTPS e entrega CSS/vídeos
      |
Waitress ......... executa a aplicação (Django) em 127.0.0.1:8000
      |
SQLite ........... um único arquivo com todos os dados:
                   C:\Academia\dados\academia.sqlite3
```

O banco de dados é **SQLite**: não há servidor de banco para instalar, configurar ou proteger com senha. O banco é um arquivo, e os PDFs dos cursos ficam numa pasta ao lado dele. Fazer backup é copiar esses dois itens do jeito certo (o manual já traz o script).

## Os manuais

Siga nesta ordem:

| Ordem | Manual | Quando usar |
|---|---|---|
| 1 | [Instalar no Windows Server](01_INSTALAR_WINDOWS_SERVER.md) | Sempre |
| 2 | [Trazer os dados atuais](02_TRANSFERIR_DADOS.md) | Somente se houver cadastros, cursos e certificados que precisam ser mantidos. O manual 1 avisa em que momento fazer isso. |

Depois da instalação, entregue aos responsáveis o [Manual do usuário](../uso/MANUAL_USUARIO.md) e o [Manual do superadmin](../uso/MANUAL_SUPERADMIN.md).

## Servidor necessário

- **Windows Server 2022 ou 2025**, 64 bits, com interface gráfica (não use Server Core).
- Ponto de partida: 2 CPUs, 4 GB de RAM e 40 GB livres em SSD. Aumente o disco conforme o volume de PDFs e de backups.
- O servidor não deve hospedar outro site nas portas 80 e 443. Se hospedar, a TI precisa adaptar o Caddy ao proxy existente.

> **Limite do SQLite:** ele grava uma coisa por vez. Para uma plataforma de treinamento com dezenas de pessoas usando ao mesmo tempo, isso é suficiente. Se a empresa planeja centenas de técnicos fazendo prova no mesmo minuto, avise o responsável pela plataforma antes de instalar.

## Ficha para preencher antes de começar

Peça estes dados à TI. Não escreva senhas nesta ficha; elas devem ser entregues por um canal reservado.

| Informação | Exemplo | Valor real |
|---|---|---|
| Endereço do site | `treinamentos.suaempresa.com.br` | __________________ |
| IP interno fixo do servidor | `192.168.10.50` | __________________ |
| Servidor SMTP, porta e usuário | `smtp.suaempresa.com.br`, 587 | __________________ |
| E-mail remetente autorizado | `treinamentos@suaempresa.com.br` | __________________ |
| E-mail da TI (para o certificado HTTPS) | `ti@suaempresa.com.br` | __________________ |
| Onde guardar a cópia externa dos backups | NAS, cofre corporativo | __________________ |
| Começar vazio ou trazer os dados atuais? | Decisão do responsável | __________________ |

## O que a TI precisa liberar na rede

1. Um registro **DNS do tipo A** apontando o endereço do site para o IP público da empresa.
2. No firewall/roteador, encaminhar as portas **TCP 80 e 443** para o IP interno do servidor.
3. **Não** abrir para a internet a porta 8000 (aplicação) nem a 2019 (administração do Caddy).
4. Permitir que o servidor acesse a internet para baixar programas, emitir o certificado HTTPS e enviar e-mails (SMTP).
5. Se a internet da empresa estiver atrás de **CGNAT**, o encaminhamento de portas não funciona; a TI precisa resolver isso com a operadora antes.

## Como ler os manuais

- Execute os passos **em ordem**, no servidor.
- Cada bloco cinza é um comando para copiar e colar no **PowerShell como administrador**. Rode um bloco por vez.
- Depois de cada bloco há um **Resultado esperado**. Se o resultado for diferente, pare e veja a seção de problemas no fim do manual.
- Onde aparecer `SUBSTITUA_...`, troque pelo valor real.
- Mantenha os caminhos `C:\Academia` e `C:\Python313` exatamente como estão; os passos seguintes dependem deles.

## Quando a instalação está pronta

Considere concluído somente depois de conferir:

- [ ] O site abre com HTTPS de dentro da empresa e de fora (ex.: celular sem Wi-Fi).
- [ ] O administrador entra no sistema.
- [ ] Um técnico de teste faz o primeiro acesso, conclui um curso e recebe o certificado.
- [ ] O PDF do curso abre para quem está logado e **não** abre sem login.
- [ ] O e-mail de "Esqueci minha senha" chega.
- [ ] Depois de reiniciar o servidor, o site volta sozinho.
- [ ] Um backup foi gerado, copiado para fora do servidor e testado.
