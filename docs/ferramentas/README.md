# Ferramentas da documentação

Esses programas geram ou verificam os manuais. Não instalam a plataforma nem devem ser executados como comandos de produção.

| Ferramenta | Função | Saída |
|---|---|---|
| `gerar_html.mjs` | Converte as fontes Markdown em páginas | `docs/publicados/instalacao/` |
| `empacotar.py` | Monta o pacote independente para entrega | `docs/distribuicao/` |
| `verificar.py` | Confere sintaxe dos exemplos e links HTML locais, sem executar os exemplos | `docs/testes/validacao-manuais/` |
| `revisar.mjs` | Abre os HTML em navegador de revisão e gera evidências | `docs/testes/validacao-manuais/evidencias/` |

## Atualizar a publicação

Na raiz do projeto, com Node.js, Python e o pacote `marked` disponíveis:

```text
node docs/ferramentas/gerar_html.mjs CAMINHO_ABSOLUTO_DO_MARKED_ESM
python -B docs/ferramentas/empacotar.py
```

O primeiro argumento é o arquivo `lib/marked.esm.js` da instalação do pacote `marked`. Primeiro gere HTML, depois o ZIP. As fontes são lidas de `docs/instalacao/` e `docs/uso/`. O ZIP inclui fontes, HTML, manuais de apoio e registro de validação; não inclui scripts nem capturas de revisão.

## Conferir a publicação

```text
python -B docs/ferramentas/verificar.py
node docs/ferramentas/revisar.mjs CAMINHO_ABSOLUTO_PLAYWRIGHT_INDEX_MJS CAMINHO_EXECUTAVEL_CHROMIUM
```

O verificador de sintaxe está preparado para Windows com PowerShell e Git Bash em `C:\Program Files\Git\bin\bash.exe`. A revisão visual exige Playwright e Chromium compatíveis, indicados nos argumentos. Ajuste esses caminhos se o ambiente de manutenção for diferente.

As ferramentas atualizam seus próprios resultados de validação e arquivos gerados. Nenhuma deve ser confundida com os scripts de instalação presentes nos manuais.
