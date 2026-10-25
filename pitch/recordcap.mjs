/**
 * Record the demo with Cap, driving a real OS cursor.
 *
 * Playwright's own video capture draws the page but not the pointer, so it can
 * never show a cursor travelling to a control. Cap records the window as the
 * compositor presents it, pointer included. So Chrome is opened as a bare app
 * window, `cliclick` moves the physical mouse onto real DOM targets, and Cap
 * records the take. Page scrolling goes through CDP wheel events while the
 * cursor hovers, which is what a person reading a screen actually does.
 *
 * Each action is timed against the narration phrase it belongs to, so the
 * pointer arrives on an element exactly when the narrator names it.
 */
import { execFileSync, spawn } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const CAP = '/Users/YACINE/.cap/bin/cap';
const CLICK = '/opt/homebrew/bin/cliclick';
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const BASE = 'http://localhost:8781';
const OUT = join(ROOT, 'out');
const PROJ = join(ROOT, 'cap');
const CDP_PORT = 9700;

// The product is designed for a 1440px-wide layout but this display is only
// 1147 CSS px, so a 1103px window is the widest that fits on screen.
const WIN = { width: 1103, height: 675 };

const NAV_LABEL = {
  home: "What's happening", agents: 'Agents at work', orchestrator: 'The orchestrator',
  reasoning: 'Agents at work',
  gate: 'Decisions', cowfood: 'Cow food', herd: 'The herd', milk: 'The milk',
  infra: 'Water & machines', how: 'How it works', close: 'Agents at work',
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const escapeRe = (t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const only = new Set(process.argv.slice(2));

const SPEECH = (() => {
  const raw = JSON.parse(readFileSync(join(ROOT, 'audio', 'durations.json'), 'utf8'));
  const per = {};
  for (const p of raw.phrases) per[p.beat] = (per[p.beat] ?? 0) + Number(p.duration ?? 0);
  return per;
})();
const CHOREO = JSON.parse(readFileSync(join(ROOT, 'choreography.json'), 'utf8')).beats;

const sh = (cmd, args) => execFileSync(cmd, args, { encoding: 'utf8' });

/** DOM element centre, in the physical screen coordinates cliclick wants. */
async function screenPoint(page, target) {
  const m = await page.evaluate(() => ({
    sx: window.screenX, sy: window.screenY,
    ow: window.outerWidth, oh: window.outerHeight,
    iw: window.innerWidth, ih: window.innerHeight,
  }));
  const insetY = m.oh - m.ih; // window title bar
  const insetX = m.ow - m.iw;

  // Prefer semantic roles before falling back to loose text. `text=` is a
  // substring match: "Approve" also matched "What you've approved", and an
  // agent's name matches the coordinator node before its own card. A role
  // lookup picks the control or the card heading the narrator is naming.
  const exact = new RegExp(`^\\s*${escapeRe(target)}\\s*$`);
  const candidates = [
    page.getByRole('button', { name: exact }),
    page.getByRole('heading', { name: exact }),
    page.locator(`text=${target}`),
  ];
  let loc = null;
  for (const c of candidates) {
    if (await c.count()) { loc = c.first(); break; }
  }
  if (!loc) return null;

  // Bring it into view first: a valid bounding box can still sit below the
  // fold, and the cursor would travel to a point nobody can see.
  await loc.scrollIntoViewIfNeeded().catch(() => {});
  await page.waitForTimeout(320);
  let bb = await loc.boundingBox();
  if (!bb) return null;

  // scrollIntoView is minimal, so the element can end up flush against the
  // top edge underneath the sticky decision strip. Nudge the page until it
  // sits comfortably in frame.
  const vh = await page.evaluate(() => window.innerHeight);
  const top = 96, bottom = vh - 96;
  if (bb.y < top || bb.y + bb.height > bottom) {
    const shift = bb.y < top ? bb.y - top : bb.y + bb.height - bottom;
    await page.evaluate((d) => window.scrollBy(0, d), shift);
    await page.waitForTimeout(220);
    bb = await loc.boundingBox();
    if (!bb) return null;
  }
  if (bb.y < 0 || bb.y > vh) return null;

  return {
    x: Math.round(m.sx + insetX / 2 + bb.x + bb.width / 2),
    y: Math.round(m.sy + insetY + bb.y + bb.height / 2),
  };
}

async function act(page, step) {
  if (step.do === 'scrollTo') {
    const p = await page.evaluate(() => ({ x: window.innerWidth / 2, y: window.innerHeight / 2 }));
    await page.mouse.move(p.x, p.y);
    await page.evaluate((y) => window.scrollTo({ top: y, behavior: 'smooth' }), step.y);
    await page.waitForTimeout(step.wait ?? 1300);
    return;
  }
  if (step.do === 'scroll') {
    const p = await page.evaluate(() => ({ x: window.innerWidth / 2, y: window.innerHeight / 2 }));
    await page.mouse.move(p.x, p.y);
    if (step.steps) {
      // Slow crawl, so a viewer can read each card as it passes.
      const per = step.dy / step.steps;
      for (let i = 0; i < step.steps; i++) {
        await page.mouse.wheel(0, per);
        await page.waitForTimeout(step.pause ?? 400);
      }
    } else {
      await page.mouse.wheel(0, step.dy);
    }
    return;
  }

  if (step.do === 'chat') {
    // Open a specialist's drawer, type a question with the real keyboard, and
    // send it — all on screen, so the video shows the feature being used
    // rather than a still of it.
    const card = page.locator('article').filter({ hasText: step.agentLabel }).first();
    const askBtn = card.getByRole('button', { name: /^ask$/i }).first();
    await askBtn.scrollIntoViewIfNeeded().catch(() => {});
    await sleep(300);

    const m = await page.evaluate(() => ({
      sx: window.screenX, sy: window.screenY,
      ow: window.outerWidth, oh: window.outerHeight,
      iw: window.innerWidth, ih: window.innerHeight,
    }));
    const bb = await askBtn.boundingBox();
    if (bb) {
      const x = Math.round(m.sx + (m.ow - m.iw) / 2 + bb.x + bb.width / 2);
      const y = Math.round(m.sy + (m.oh - m.ih) + bb.y + bb.height / 2);
      sh(CLICK, ['-e', '1.1', `m:${x},${y}`]);
      await sleep(260);
      sh(CLICK, [`c:${x},${y}`]);
    }
    await sleep(650);

    await page.locator('textarea').first().click().catch(() => {});
    await page.keyboard.type(step.ask, { delay: 14 });
    await sleep(350);
    await page.getByRole('button', { name: /^Ask$/ }).first().click().catch(() => {});
    console.log(`    · chat "${step.ask.slice(0, 46)}"`);
    return;
  }

  const pt = await screenPoint(page, step.target);
  if (!pt) { console.log(`    ! no element "${step.target}"`); return; }

  // Eased motion so the travel reads as a hand, not a teleport. Then confirm
  // the pointer actually arrived: the window server intermittently drops a
  // move, and a silently-missed target is exactly the failure that makes the
  // demo point at the wrong thing while the narrator names it.
  const read = () => sh(CLICK, ['-d', 'stdout', 'p:.']).trim().split(',').map(Number);
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

  sh(CLICK, ['-e', '1.2', `m:${pt.x},${pt.y}`]);
  await sleep(140);
  let pos = read();
  for (let attempt = 0; attempt < 3 && dist(pos, [pt.x, pt.y]) > 24; attempt++) {
    sh(CLICK, [`m:${pt.x},${pt.y}`]); // direct, no easing, as a correction
    await sleep(160);
    pos = read();
  }
  if (dist(pos, [pt.x, pt.y]) > 24) {
    console.log(`    ! ${step.target}: cursor at ${pos}, wanted ${pt.x},${pt.y}`);
  }

  if (step.do === 'click') {
    await sleep(380);
    sh(CLICK, [`c:${pt.x},${pt.y}`]);
  }
  console.log(`    · ${step.do} "${step.target}" @ ${pt.x},${pt.y}`);
}

async function record(beatId) {
  const dur = Math.ceil(SPEECH[beatId] ?? 10) + 1;
  const proj = join(PROJ, `${beatId}.cap`);
  rmSync(proj, { recursive: true, force: true });
  mkdirSync(PROJ, { recursive: true });
  mkdirSync(OUT, { recursive: true });

  const profile = `/tmp/capchrome_${beatId}`;
  rmSync(profile, { recursive: true, force: true });
  const chrome = spawn(CHROME, [
    `--app=${BASE}`,
    `--window-size=${WIN.width},${WIN.height}`,
    '--window-position=0,40',
    `--remote-debugging-port=${CDP_PORT}`,
    `--user-data-dir=${profile}`,
    '--no-first-run', '--no-default-browser-check',
  ], { stdio: 'ignore' });

  let browser = null;
  for (let i = 0; i < 40; i++) {
    try { browser = await chromium.connectOverCDP(`http://127.0.0.1:${CDP_PORT}`); break; }
    catch { await sleep(500); }
  }
  if (!browser) { chrome.kill(); throw new Error('chrome CDP never came up'); }

  const page = browser.contexts()[0].pages()[0];
  await page.waitForTimeout(2200);

  // Refuse to record a page that did not load. A stopped backend produces
  // Chrome's "This site can't be reached" page, which records perfectly
  // happily and only shows up as a white hole in the finished film.
  const title = await page.title().catch(() => "");
  const hasApp = await page.locator("nav[aria-label='Main']").count();
  if (!/aidustrial|adrar/i.test(title) || !hasApp) {
    await browser.close().catch(() => {});
    chrome.kill();
    throw new Error(
      `page did not load (title=${JSON.stringify(title)}). Is the server on ${BASE} running?`,
    );
  }

  const nav = page.locator('button, a').filter({ hasText: NAV_LABEL[beatId] }).first();
  if (await nav.count()) await nav.click().catch(() => {});
  await page.waitForTimeout(2600);

  const targets = JSON.parse(sh(CAP, ['targets', '--json']));
  const win = (targets.windows ?? []).find((w) => /aidustrial|adrar/i.test(w.name ?? ''));
  if (!win) { await browser.close().catch(() => {}); chrome.kill(); throw new Error('no app window'); }

  console.log(`[cap] ${beatId}: window ${win.id}, ${dur}s`);
  const rec = spawn(CAP, [
    'record', 'start', '--window', String(win.id), '--path', proj,
    '--fps', '30', '--duration', String(dur),
  ], { stdio: ['ignore', 'ignore', 'inherit'] });

  const t0 = Date.now();
  const steps = [...(CHOREO[beatId]?.actions ?? [])].sort((a, b) => a.at - b.at);
  for (const step of steps) {
    const wait = step.at * 1000 - (Date.now() - t0);
    if (wait > 0) await sleep(wait);
    await act(page, step).catch((e) => console.log('    !', e.message));
  }

  const leftover = dur * 1000 - (Date.now() - t0);
  if (leftover > 0) await sleep(leftover);
  rec.kill('SIGINT');
  await sleep(2200);

  const dest = join(OUT, `${beatId}.mp4`);
  sh(CAP, ['export', proj, '-o', dest, '--resolution', '1920x1080', '--fps', '30',
    '--quality', 'maximum']);
  console.log(`[cap] ${beatId} -> ${dest}`);

  await browser.close().catch(() => {});
  chrome.kill();
}

const ids = only.size ? [...only] : Object.keys(NAV_LABEL);
for (const id of ids) await record(id);
console.log('[cap] all done');
