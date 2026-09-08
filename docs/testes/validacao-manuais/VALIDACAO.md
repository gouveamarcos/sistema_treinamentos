# Registro de revisão dos manuais

Edição: 08/09/2026.

Foram produzidos quatro manuais de instalação, um guia inicial e um apêndice de transferência de dados. As versões HTML são geradas das fontes Markdown e incluem navegação e impressão pelo navegador.

## Verificações realizadas

- Leitura da configuração, dependências, rotas, comandos administrativos e migrações do projeto.
- Consulta à documentação oficial de Django, PostgreSQL, Ubuntu, Python, Waitress, Caddy, WinSW e Microsoft.
- Análise de sintaxe, sem execução, dos 28 blocos PowerShell, 37 blocos Bash, três blocos Python, dois exemplos XML e um JSON.
- Conferência de links locais e âncoras das versões HTML.
- Abertura das seis páginas principais em navegador sem interface, inspeção de imagens e verificação de largura em computador e celular.
- Conferência de que as alterações desta entrega ficaram na pasta de documentação de instalação.

## Limites da revisão

Não houve instalação de PostgreSQL, Caddy, Waitress ou Gunicorn para operar a plataforma nesta entrega. Não foram criados usuários, migrados bancos, enviados e-mails, abertas portas ou alteradas permissões da aplicação existente.

Os blocos SQL e as configurações Caddy/systemd foram revisados por leitura e comparação com as fontes; não executados contra serviços reais. A validação de sintaxe de scripts não comprova conectividade, credenciais, permissões do servidor nem capacidade de atendimento.

O instalador deve executar os testes locais e externos, de e-mail, reinício e restauração indicados nos manuais antes de considerar a implantação concluída.
