// Markdown/browser rendering generalized from C001's approved export path.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL, fileURLToPath} from 'node:url';

const require = createRequire(import.meta.url);
const {marked} = await import(pathToFileURL(require.resolve('marked')).href);
const {chromium} = require('playwright');
const job = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const cfg = job.config;
const escape = text => String(text).replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
const images = [];
const renderer = new marked.Renderer();
renderer.html = ({text}) => escape(text);
renderer.image = ({href, text}) => {
  if (/^[a-z][a-z0-9+.-]*:/i.test(href) && !href.startsWith('file:')) throw Error('图片必须为实际本地文件：' + href);
  const file = href.startsWith('file:') ? fileURLToPath(href) : path.resolve(path.dirname(job.source), decodeURIComponent(href));
  const mime = {'.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.webp':'image/webp', '.svg':'image/svg+xml'}[path.extname(file).toLowerCase()];
  if (!mime) throw Error('不支持的图片格式：' + file);
  images.push({file, alt: text});
  return `<img src="data:${mime};base64,${fs.readFileSync(file).toString('base64')}" alt="${escape(text)}">`;
};

const browser = await chromium.launch({headless:true});
try {
  const page = await browser.newPage();
  const fontSession = await page.context().newCDPSession(page);
  await fontSession.send('DOM.enable');
  await fontSession.send('CSS.enable');
  const result = {parts:[], watermarks:{}, images};
  for (const [index, segment] of job.segments.entries()) {
    const dims = cfg.pages[segment.orientation];
    const [top, right, bottom, left] = dims.margin_mm;
    const headings = cfg.heading_pt.map((size, i) => `h${i+1}{font-size:${size}pt;font-weight:${cfg.heading_weight};line-height:1.45;margin:${i ? 18 : 0}pt 0 10pt;break-after:avoid}`).join('');
    const css = `@page{size:${dims.width_mm}mm ${dims.height_mm}mm;margin:${top}mm ${right}mm ${bottom}mm ${left}mm}*{box-sizing:border-box}body{margin:0;background:white;color:#111;font-family:${JSON.stringify(cfg.font_family)},sans-serif;font-size:${cfg.font_pt}pt;line-height:${cfg.line_height};-webkit-print-color-adjust:exact;print-color-adjust:exact}${headings}p{margin:0 0 8pt;orphans:3;widows:3}li{margin-bottom:3pt}table{width:100%;border-collapse:collapse;font-size:9.5pt;margin:10pt 0}thead{display:table-header-group}tr{break-inside:avoid}th,td{border:0.5pt solid #aaa;padding:5pt;text-align:left;vertical-align:top;overflow-wrap:anywhere}th{background:#f4f4f4}img{display:block;max-width:100%;max-height:${dims.image_max_height_mm}mm;width:auto;height:auto;margin:8pt auto;object-fit:contain;break-inside:avoid}a{color:inherit;text-decoration:none}pre{white-space:pre-wrap;overflow-wrap:anywhere}blockquote{margin-left:0;padding-left:10pt;border-left:1pt solid #aaa}`;
    const html = `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>${css}</style><body><main>${marked.parse(segment.markdown, {renderer, breaks:true})}</main></body></html>`;
    const htmlFile = path.join(job.work, `part-${index}.html`);
    fs.writeFileSync(htmlFile, html);
    await page.goto(pathToFileURL(htmlFile).href);
    await page.emulateMedia({media:'print'});
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(() => Promise.all([...document.images].map(image => image.decode())));
    const loaded = await page.locator('img').evaluateAll(els => els.map(el => ({width:el.naturalWidth, height:el.naturalHeight, drawnWidth:el.getBoundingClientRect().width, drawnHeight:el.getBoundingClientRect().height})));
    if (loaded.some(i => !i.width || !i.height || Math.abs(i.width/i.height-i.drawnWidth/i.drawnHeight)>0.01)) throw Error('图片加载或显示比例异常');
    const text = await page.locator('main').innerText();
    const {root} = await fontSession.send('DOM.getDocument');
    const {nodeIds} = await fontSession.send('DOM.querySelectorAll', {nodeId:root.nodeId, selector:'main h1,main h2,main h3,main h4,main h5,main h6,main p,main li,main td,main th,main strong,main code'});
    const fonts = [];
    for (const nodeId of nodeIds) fonts.push(...(await fontSession.send('CSS.getPlatformFontsForNode', {nodeId})).fonts);
    const pdf = path.join(job.work, `part-${index}.pdf`);
    await page.pdf({path:pdf, preferCSSPageSize:true, printBackground:true, displayHeaderFooter:false});
    result.parts.push({file:pdf, orientation:segment.orientation, text, images:loaded, fonts});
  }
  for (const orientation of new Set(job.segments.map(s => s.orientation))) {
    const dims = cfg.pages[orientation], wm = cfg.watermark;
    const css = `@page{size:${dims.width_mm}mm ${dims.height_mm}mm;margin:0}html,body{margin:0;background:transparent;font-family:${JSON.stringify(cfg.font_family)},sans-serif}.wm{position:absolute;transform:translate(-50%,-50%) rotate(-${wm.angle_degrees}deg);font-size:${wm.font_pt}pt;font-weight:${wm.font_weight};white-space:nowrap;line-height:1;color:${wm.color};opacity:${wm.opacity}}`;
    const body = wm.positions_mm[orientation].map(([x,y]) => `<div class="wm" style="left:${x}mm;top:${y}mm">${escape(wm.text)}</div>`).join('');
    const htmlFile = path.join(job.work, `watermark-${orientation}.html`);
    fs.writeFileSync(htmlFile, `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>${css}</style><body>${body}</body></html>`);
    await page.goto(pathToFileURL(htmlFile).href);
    await page.evaluate(() => document.fonts.ready);
    const pdf = path.join(job.work, `watermark-${orientation}.pdf`);
    await page.pdf({path:pdf, preferCSSPageSize:true, printBackground:true, displayHeaderFooter:false});
    result.watermarks[orientation] = pdf;
  }
  fs.writeFileSync(job.result, JSON.stringify(result, null, 2));
} finally {
  await browser.close();
}
