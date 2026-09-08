# Documentação da Academia Técnica

Escolha o material conforme sua atividade. Os arquivos editáveis ficam separados das páginas geradas, ferramentas e pacotes de entrega.

| Preciso de… | Onde encontrar |
|---|---|
| Usar a plataforma como técnico | [Manual do usuário](uso/MANUAL_USUARIO.md) |
| Administrar a plataforma | [Manual do superadmin](uso/MANUAL_SUPERADMIN.md) |
| Instalar no servidor | [Comece aqui: Windows ou Ubuntu](instalacao/00_LEIA_PRIMEIRO.md) |
| Ler e imprimir os manuais no navegador | [Índice dos manuais publicados](publicados/instalacao/index.html) |
| Entregar os manuais à equipe instaladora | [Pacote ZIP completo](distribuicao/Manuais_Instalacao_Academia_Tecnica.zip) |
| Testar o funcionamento | [Roteiro de testes ponta a ponta](testes/ROTEIROS_TESTE_E2E.md) |
| Conferir a revisão dos manuais | [Registro de validação](testes/validacao-manuais/VALIDACAO.md) |
| Atualizar as páginas e o ZIP | [Ferramentas de documentação](ferramentas/README.md) |

## Organização

```text
docs/
├── README.md                 Índice geral
├── uso/                      Manuais para técnicos e administradores
├── instalacao/               Fontes dos manuais de instalação e transferência
├── testes/                   Roteiros e registros de validação
│   └── validacao-manuais/
│       ├── evidencias/       Imagens e resultados das verificações
│       └── temporarios/      Fragmentos antigos de conferência preservados
├── ferramentas/              Geradores, empacotador e verificadores
├── publicados/
│   └── instalacao/           HTML para leitura e impressão
│       └── apoio/            Cópias geradas dos manuais de uso para distribuição
└── distribuicao/             ZIP pronto para entregar
```

## Manuais de instalação

Execute apenas o par correspondente ao sistema do servidor:

| Sistema | Banco de dados | Plataforma |
|---|---|---|
| Windows Server 2022/2025 | [PostgreSQL](instalacao/01_POSTGRESQL_WINDOWS.md) | [Plataforma](instalacao/02_PLATAFORMA_WINDOWS.md) |
| Ubuntu Server 24.04 | [PostgreSQL](instalacao/03_POSTGRESQL_UBUNTU.md) | [Plataforma](instalacao/04_PLATAFORMA_UBUNTU.md) |

Para preservar os cadastros existentes, consulte [Transferência de dados](instalacao/05_TRANSFERIR_DADOS_EXISTENTES.md).

## Como manter a documentação

- Edite os originais em `uso/`, `instalacao/` e `testes/`.
- Gere novamente o HTML e o ZIP depois de atualizar os originais; não edite suas cópias separadamente.
- As cópias em `publicados/instalacao/apoio/` existem para que o pacote funcione fora do projeto. Os originais são os de `uso/`.
- Evidências e fragmentos de verificação não são instruções de instalação.
- Para implantação em servidor, siga os manuais de `instalacao/`; o roteiro E2E também contém preparação de ambiente local de testes.

Esta reorganização preserva o conteúdo dos manuais. A revisão de conteúdo apontada anteriormente permanece pendente: a orientação sobre validade zero no manual do superadmin e seus trechos resumidos de implantação/backup precisam ser alinhados ao comportamento atual e aos manuais específicos.
