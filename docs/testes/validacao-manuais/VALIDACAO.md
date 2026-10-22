# Registro de revisão dos manuais

Edição: 22/10/2026.

Os manuais de instalação foram reescritos para **Windows Server com SQLite**: um guia inicial (00), o manual de instalação (01) e o de transferência de dados (02). Os manuais anteriores, para PostgreSQL e Ubuntu, foram movidos para `docs/instalacao/antigos_postgresql/`.

## Verificações realizadas

Em ambiente Linux com Python 3.13 e Django 6.0.5:

- Suíte automática do projeto (130 testes), incluindo os novos testes de configuração SQLite, PDF protegido e `redefinir_admin`.
- Sintaxe do `ambiente.json`, dos dois programas Python (`executar.py`, `backup.py`) e dos dois XML do WinSW.
- `Caddyfile` validado com `caddy validate` (Caddy 2.8.4).
- Iniciador `executar.py` com a configuração do manual: `migrate`, leitura de `DEBUG` e do caminho do banco, Waitress respondendo `/saude/`, redirecionamento para HTTPS e PDF exigindo login.
- `backup.py`: cópia consistente do banco, verificação de integridade, cópia dos PDFs e remoção das cópias antigas.
- Comandos de conferência do Manual 2 executados sobre uma cópia do banco atual.
- `redefinir_admin` com senha recusada (nada é alterado) e com senha válida.

## Limites da revisão

Não houve execução em Windows Server. Não foram testados os comandos PowerShell, `icacls`, a instalação dos serviços pelo WinSW, a emissão de certificado pelo Caddy, o Agendador de Tarefas nem o envio real de e-mails.

O instalador deve executar os testes de aceite do Manual 1 (Passos 13, 14 e 17) e uma restauração de backup antes de considerar a implantação concluída.
