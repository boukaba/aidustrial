import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const OUT = process.argv[2] || 'Aidustrial_pitch_deck.pdf';

const b = await chromium.launch({ headless: true });
const p = await b.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 2 });
await p.goto(`file://${join(ROOT, 'deck.html')}`, { waitUntil: 'networkidle' });
await p.waitForTimeout(2200);

// Report any slide whose real content would clip.
const rows = await p.$$eval('section.slide', (els) =>
  els.map((e, i) => {
    const box = e.getBoundingClientRect();
    let low = 0;
    for (const c of e.children) {
      if (c.classList.contains('rail') || c.classList.contains('glow')) continue;
      low = Math.max(low, c.getBoundingClientRect().bottom - box.top);
    }
    return { i: i + 1, content: Math.round(low), over: low > box.height - 20 };
  }),
);
for (const r of rows) {
  if (r.over) console.log(`  ! slide ${r.i} overflows (content bottom ${r.content})`);
}

await p.pdf({
  path: join(ROOT, OUT),
  width: '1280px',
  height: '720px',
  printBackground: true,
  margin: { top: '0px', bottom: '0px', left: '0px', right: '0px' },
  // Document properties, so the deck identifies itself outside a browser tab.
  title: 'Aidustrial, Pitch Deck',
  author: 'Mohammed Boukaba',
  subject:
    'An agentic operations layer for large industrial farms: seven specialist AI Agents ' +
    'working 24/7, escalating consequential decisions to humans.',
  keywords: 'Aidustrial, AI Agents, human-in-the-loop, digital twin, RAG, Baladna, Adrar, Thirduni',
  creator: 'Aidustrial',
});
await b.close();

// Chromium drops the author/subject options, so stamp them on the file. Run as
// part of the build so a re-render cannot silently lose the document metadata.
execFileSync('python3', [join(ROOT, 'pdfmeta.py'), OUT], { stdio: 'inherit' });
console.log(`pdf written: ${OUT} (${rows.length} slides)`);
