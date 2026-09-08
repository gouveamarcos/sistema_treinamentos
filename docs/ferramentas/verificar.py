"""Static validation only. Does not execute installation commands."""
import ast
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

docs = Path(__file__).resolve().parents[1]
root = docs / 'instalacao'
qa = docs / 'testes' / 'validacao-manuais'
(qa / 'temporarios').mkdir(parents=True, exist_ok=True)
(qa / 'evidencias').mkdir(parents=True, exist_ok=True)
counts = {}
errors = []

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
        self.code = []
        self.in_code = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        if tag == 'a' and 'href' in attrs:
            self.links.append(attrs['href'])
        if tag == 'code':
            self.in_code = True
    def handle_endtag(self, tag):
        if tag == 'code':
            self.in_code = False
    def handle_data(self, data):
        if self.in_code:
            self.code.append(data)

for source in sorted(root.glob('[0-9][0-9]_*.md')):
    md = source.read_text(encoding='utf-8')
    if md.count('```') % 2:
        errors.append(f'{source.name}: unbalanced fence')
    blocks = re.findall(r'^```([^\n]*)\n(.*?)^```', md, flags=re.M | re.S)
    for index, (language, code) in enumerate(blocks, 1):
        counts[language] = counts.get(language, 0) + 1
        try:
            if language == 'python':
                ast.parse(code)
            elif language == 'json':
                json.loads(code)
            elif language == 'xml':
                ET.fromstring(code)
            elif language == 'bash':
                proc = subprocess.run(
                    [r'C:\Program Files\Git\bin\bash.exe', '--noprofile', '--norc', '-n'],
                    input=code, text=True, capture_output=True)
                if proc.returncode:
                    raise ValueError(proc.stderr)
            elif language == 'powershell':
                snippet = qa / 'temporarios' / 'snippet.ps1'
                snippet.write_text(code, encoding='utf-8-sig')
                quoted_path = "'" + str(snippet).replace("'", "''") + "'"
                parser = "$t=$null; $e=$null; [System.Management.Automation.Language.Parser]::ParseFile(" + quoted_path + ", [ref]$t, [ref]$e) | Out-Null; if ($e.Count) { $e | ForEach-Object { $_.Message }; exit 1 }"
                # Fixed parser, never dot-source or execute the supplied snippet.
                proc = subprocess.run(['powershell.exe', '-NoProfile', '-Command', parser], text=True, capture_output=True)
                if proc.returncode:
                    raise ValueError(proc.stdout + proc.stderr)
        except Exception as exc:
            errors.append(f'{source.name} block {index} ({language}): {exc}')

for source in [docs.parent / 'README.md', *docs.rglob('*.md')]:
    content = re.sub(r'^```.*?^```', '', source.read_text(encoding='utf-8'), flags=re.M | re.S)
    for target in re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', content):
        if target.startswith(('https:', 'http:', 'mailto:', '#')):
            continue
        target = target.split('#', 1)[0]
        if target and not (source.parent / target).exists():
            errors.append(f'{source.name}: broken Markdown link {target}')

for document in (docs / 'publicados').rglob('*.html'):
    parser = Links()
    parser.feed(document.read_text(encoding='utf-8'))
    for href in parser.links:
        if href.startswith(('http:', 'https:', 'mailto:')):
            continue
        target, _, fragment = href.partition('#')
        if target and not (document.parent / target).exists():
            errors.append(f'{document.name}: broken link {href}')
        if not target and fragment and fragment not in parser.ids:
            errors.append(f'{document.name}: missing anchor {href}')

report = {'validated_blocks': counts, 'errors': errors, 'scope': 'Syntax and local links only; no installation, database connection, or service operation executed.'}
(qa / 'evidencias' / 'validacao.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(bool(errors))
