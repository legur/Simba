import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { closeServer, openDemo } from '../engine/render/page.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const fixture = path.join(here, 'fixtures', 'anime-seek');
const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'simba-motion-seek-'));

try {
  for (const motion of ['anime', 'classic']) {
    const runFixture = path.join(tempRoot, motion);
    fs.cpSync(fixture, runFixture, { recursive: true });
    const timelinePath = path.join(runFixture, 'timeline.json');
    const timeline = JSON.parse(fs.readFileSync(timelinePath, 'utf8'));
    timeline.motion = motion;
    fs.writeFileSync(timelinePath, JSON.stringify(timeline));
    const { browser, page } = await openDemo(runFixture, { w: 1080, h: 1920, warnings: true });
    try {
      const hashes = new Map();
      for (const t of [0.55, 1.9, 2.95, 0.55, 1.9, 2.95]) {
        await page.evaluate(async time => {
          await window.prepare?.(time);
          window.render(time);
        }, t);
        const hash = crypto.createHash('sha256').update(await page.screenshot({ type: 'png' })).digest('hex');
        if (hashes.has(t)) assert.equal(hash, hashes.get(t), `${motion} frame at ${t}s changed after out-of-order seek`);
        else hashes.set(t, hash);
      }
      assert.equal(await page.evaluate(() => typeof window.TEXTS), 'function');
      console.log(`${motion} seek render: ${hashes.size} deterministic Chromium frames`);
    } finally {
      await browser.close();
    }
  }
} finally {
  closeServer();
  fs.rmSync(tempRoot, { recursive: true, force: true });
}
