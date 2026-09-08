import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const { chromium } = await import(pathToFileURL(process.argv[2]).href);
const docs = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const root = path.join(docs, 'publicados', 'instalacao');
const evidence = path.join(docs, 'testes', 'validacao-manuais', 'evidencias');
fs.mkdirSync(evidence, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: process.argv[3] });
const page = await browser.newPage({ viewport: { width: 1400, height: 1100 }, deviceScaleFactor: 1 });
const report = [];
for (const file of fs.readdirSync(root).filter(n => /^\d\d_.*\.html$/.test(n))) {
  await page.goto(pathToFileURL(path.join(root, file)).href);
  const result = await page.evaluate(() => ({
    title: document.title,
    sections: document.querySelectorAll('h2').length,
    bodyWidth: document.body.scrollWidth,
    viewport: innerWidth,
    codeBlocks: document.querySelectorAll('pre').length,
    emptyLinks: [...document.querySelectorAll('a')].filter(a => !a.textContent.trim()).length,
  }));
  await page.screenshot({ path: path.join(evidence, file.replace('.html', '.png')) });
  report.push({ file, ...result });
}
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(pathToFileURL(path.join(root, '02_PLATAFORMA_WINDOWS.html')).href);
await page.screenshot({ path: path.join(evidence, 'windows-mobile.png') });
report.push(await page.evaluate(() => ({ mobileWidth: document.body.scrollWidth, viewport: innerWidth })));
await browser.close();
fs.writeFileSync(path.join(evidence, 'visual.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report));
