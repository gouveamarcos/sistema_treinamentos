# Documentação da Academia Técnica

Escolha o material conforme sua atividade. Os arquivos editáveis ficam separados das páginas geradas, ferramentas e pacotes de entrega.

| Preciso de… | Onde encontrar |
|---|---|
| Usar a plataforma como técnico | [Manual do usuário](uso/MANUAL_USUARIO.md) |
| Administrar a plataforma | [Manual do superadmin](uso/MANUAL_SUPERADMIN.md) |
| Instalar no servidor | [Comece aqui: Windows Server](instalacao/00_LEIA_PRIMEIRO.md) |
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
│   └── antigos_postgresql/   Manuais anteriores (PostgreSQL/Ubuntu), fora de uso
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

A plataforma é instalada em **Windows Server**, com banco **SQLite** (um arquivo, sem servidor de banco):

| Ordem | Manual |
|---|---|
| 0 | [Comece aqui](instalacao/00_LEIA_PRIMEIRO.md) |
| 1 | [Instalar no Windows Server](instalacao/01_INSTALAR_WINDOWS_SERVER.md) |
| 2 | [Trazer os dados atuais](instalacao/02_TRANSFERIR_DADOS.md) (somente se for manter os dados) |

Os manuais antigos, para PostgreSQL e Ubuntu, ficaram em `instalacao/antigos_postgresql/` apenas como referência.

## Como manter a documentação

- Edite os originais em `uso/`, `instalacao/` e `testes/`.
- Gere novamente o HTML e o ZIP depois de atualizar os originais; não edite suas cópias separadamente.
- As cópias em `publicados/instalacao/apoio/` existem para que o pacote funcione fora do projeto. Os originais são os de `uso/`.
- Evidências e fragmentos de verificação não são instruções de instalação.
- Para implantação em servidor, siga os manuais de `instalacao/`; o roteiro E2E também contém preparação de ambiente local de testes.

Pendente de revisão: a orientação sobre validade zero no manual do superadmin.
