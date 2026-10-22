"""Build a self-contained handoff ZIP from the generated reading copies."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

docs = Path(__file__).resolve().parents[1]
root = docs / 'instalacao'
published = docs / 'publicados' / 'instalacao'
output = docs / 'distribuicao' / 'Manuais_Instalacao_Academia_Tecnica.zip'
output.parent.mkdir(parents=True, exist_ok=True)
included = []
sources = [(p, p.relative_to(published)) for p in sorted(published.rglob('*'))
           if p.is_file() and p.suffix in {'.md', '.html'}]
sources += [(p, Path(p.name)) for p in sorted(root.glob('[0-9][0-9]_*.md'))]
sources += [(docs / 'testes' / 'validacao-manuais' / 'VALIDACAO.md', Path('VALIDACAO.md'))]
with ZipFile(output, 'w', compression=ZIP_DEFLATED) as package:
    for source, relative in sources:
        data = source.read_text(encoding='utf-8')
        if source.suffix == '.md' and source.parent == root:
            data = data.replace('(../uso/MANUAL_USUARIO.md)', '(apoio/MANUAL_USUARIO.md)')
            data = data.replace('(../uso/MANUAL_SUPERADMIN.md)', '(apoio/MANUAL_SUPERADMIN.md)')
        package.writestr(relative.as_posix(), data.encode('utf-8'))
        included.append(relative.as_posix())
    package.writestr('LEIA-ME.txt', (
        'MANUAIS DE INSTALACAO - ACADEMIA TECNICA\n\n'
        '1. Extraia o ZIP inteiro para uma pasta.\n'
        '2. Abra index.html no navegador.\n'
        '3. Siga os manuais na ordem: 00, 01 e, se for manter os dados, 02.\n'
        '5. Use o botao de imprimir para salvar em PDF, se desejar.\n\n'
        'As pastas de apoio devem permanecer junto dos manuais.\n'
        'Este pacote contem apenas documentacao, sem banco, credenciais ou codigo da plataforma.\n'
        'A equipe instaladora precisa receber a entrega do projeto separadamente.\n'
    ).encode('utf-8'))
with ZipFile(output) as package:
    assert package.testzip() is None
    assert len([name for name in included if name[:2] in ('01', '02') and name.endswith('.html')]) == 2
print(f'{output}: {len(included) + 1} arquivos; {output.stat().st_size} bytes; integridade OK.')
