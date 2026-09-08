// Usage: node gerar_html.mjs ABSOLUTE_PATH_TO_MARKED_ESM
// Rebuilds only the reading copies of the installation manuals.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const docs = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const root = path.join(docs, 'instalacao');
const output = path.join(docs, 'publicados', 'instalacao');
fs.mkdirSync(output, { recursive: true });
const { marked } = await import(pathToFileURL(process.argv[2]).href);
const escape = value => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const css = `
:root{color-scheme:light;--ink:#182b3a;--accent:#005e68;--line:#d5e1e6}
*{box-sizing:border-box}body{margin:0;background:#edf2f5;color:var(--ink);font:16px/1.65 system-ui,-apple-system,Segoe UI,sans-serif}
header{background:#103841;color:white;padding:20px max(24px,calc((100vw - 1080px)/2));font-size:13px;letter-spacing:.1em;text-transform:uppercase}
.toolbar{display:flex;gap:18px;align-items:center;flex-wrap:wrap;max-width:1080px;margin:24px auto;padding:0 24px}
.toolbar a{font-weight:650}button{font:inherit;border:1px solid var(--accent);border-radius:6px;color:var(--accent);background:white;padding:8px 16px;cursor:pointer}
main{max-width:1080px;margin:0 auto 48px;background:white;padding:42px 58px;box-shadow:0 4px 24px #173a4710;border:1px solid var(--line)}
h1{font-size:34px;line-height:1.2;margin:0 0 24px;color:#103841;letter-spacing:-.035em}h2{font-size:23px;line-height:1.3;margin:40px 0 18px;padding-top:20px;border-top:2px solid var(--line);color:var(--accent)}h3{font-size:19px}
a{color:var(--accent);text-underline-offset:3px;overflow-wrap:anywhere}p,li{overflow-wrap:anywhere}li{margin:7px 0}strong{font-weight:700}
pre{background:#f1f5f7;border:1px solid var(--line);border-left:4px solid var(--accent);border-radius:5px;padding:16px 18px;overflow-x:auto;line-height:1.5}
code{font-family:Consolas,ui-monospace,monospace;font-size:.88em}p code,li code,td code{background:#eef3f5;padding:1px 4px;border-radius:3px;overflow-wrap:anywhere}
table{border-collapse:collapse;width:100%;margin:22px 0;font-size:14px;table-layout:fixed}th{background:#103841;color:white;text-align:left}td,th{border:1px solid var(--line);padding:10px 12px;vertical-align:top;overflow-wrap:anywhere}tbody tr:nth-child(even){background:#f5f8f9}
blockquote{border-left:4px solid #d7a237;margin:20px 0;padding:8px 20px;background:#fff8e8}nav{border:1px solid var(--line);background:#f7fafb;padding:18px 24px;margin:24px 0}nav ol{columns:2;column-gap:32px;font-size:14px;margin-bottom:0}nav li{break-inside:avoid;margin:3px 0}
footer{font-size:12px;color:#50636e;border-top:1px solid var(--line);margin-top:36px;padding-top:16px}
@media(max-width:700px){main{padding:24px 18px;margin:0;border:0}h1{font-size:27px}nav ol{columns:1}table{font-size:12px}td,th{padding:7px}.toolbar{margin:12px auto}}
@media print{@page{size:A4;margin:17mm 15mm}body{background:white;font:10pt/1.45 Arial,sans-serif}header,.toolbar{display:none}main{border:0;box-shadow:none;padding:0;margin:0;max-width:none}h1{font-size:23pt}h2{font-size:15pt;break-after:avoid;margin-top:24px;padding-top:12px}h3{break-after:avoid}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:8.5pt;overflow:visible;break-inside:auto}table{font-size:9pt}tr{break-inside:avoid}thead{display:table-header-group}nav{break-inside:avoid}a{color:inherit}p{orphans:3;widows:3}footer{font-size:8pt}}
`;

function render(markdown, inSupport = false) {
  let html = marked.parse(markdown, { gfm: true });
  html = html.replace(/href="([^"#]+)\.md(#[^"]*)?"/g, (all, target, anchor = '') => {
    if (/^https?:/.test(target)) return all;
    if (target.startsWith('../uso/MANUAL_')) target = 'apoio/' + path.basename(target);
    return `href="${target}.html${anchor}"`;
  });
  const headings = [];
  let i = 0;
  html = html.replace(/<h2>(.*?)<\/h2>/gs, (_, title) => {
    const id = `secao-${++i}`;
    headings.push(`<li><a href="#${id}">${title.replace(/^\d+\.\s*/, '')}</a></li>`);
    return `<h2 id="${id}">${title}</h2>`;
  });
  const title = markdown.split('\n')[0].replace(/^#\s*/, '');
  const toc = headings.length ? `<nav aria-label="Sumário"><strong>Neste manual</strong><ol>${headings.join('')}</ol></nav>` : '';
  html = html.replace(/(<\/h1>)/, `$1${toc}`);
  const home = inSupport ? '../index.html' : 'index.html';
  return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escape(title)}</title><style>${css}</style></head><body><header>Academia Técnica · Instalação e operação · Setembro 2026</header><div class="toolbar"><a href="${home}">Comece aqui / escolher o sistema</a><button onclick="window.print()">Imprimir ou salvar em PDF</button></div><main>${html}<footer>Academia Técnica • Manual de instalação • Edição 08/09/2026. Os comandos devem ser executados pelo instalador no servidor correspondente.</footer></main></body></html>`;
}

const files = fs.readdirSync(root).filter(name => /^\d\d_.*\.md$/.test(name)).sort();
for (const name of files) fs.writeFileSync(path.join(output, name.replace(/\.md$/, '.html')), render(fs.readFileSync(path.join(root, name), 'utf8')));
fs.copyFileSync(path.join(output, '00_LEIA_PRIMEIRO.html'), path.join(output, 'index.html'));
const support = path.join(output, 'apoio');
fs.mkdirSync(support, { recursive: true });
for (const name of ['MANUAL_USUARIO.md', 'MANUAL_SUPERADMIN.md']) {
  const md = fs.readFileSync(path.join(docs, 'uso', name), 'utf8');
  fs.copyFileSync(path.join(docs, 'uso', name), path.join(support, name));
  fs.writeFileSync(path.join(support, name.replace(/\.md$/, '.html')), render(md, true));
}
console.log(`Geradas ${files.length} versões HTML, índice e dois manuais de apoio.`);
