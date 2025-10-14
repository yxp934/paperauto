import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

test.setTimeout(240_000);

// Helper: wait for a substring to appear in Live Logs
async function waitForLog(page, text: string, timeoutMs = 120_000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const logs = await page.locator('h2:has-text("Live Logs") ~ *').first().innerText().catch(() => '');
    if (logs.includes(text)) return true;
    await page.waitForTimeout(500);
  }
  throw new Error(`Timed out waiting for log: ${text}`);
}

// Helper: get all logs text
async function getLogs(page): Promise<string> {
  return page.locator('h2:has-text("Live Logs") ~ *').first().innerText();
}

// Helper: extract arXiv id from logs (e.g., 2410.12345v1)
function extractArxivId(logs: string): string | null {
  const m = logs.match(/processing\s+\d+\/\d+\s+(\d{4}\.[0-9]{4,5}(?:v\d+)?)/);
  if (m) return m[1];
  const m2 = logs.match(/\b(\d{4}\.[0-9]{4,5}(?:v\d+)?)\b/);
  return m2 ? m2[1] : null;
}

// Helper: count VTT cues
function countVttCues(vtt: string): number {
  const segments = vtt.split(/\n\n+/).filter(x => x.trim().length > 0);
  // skip header line WEBVTT
  return segments.filter(s => /-->/.test(s)).length;
}

function vttDurations(vtt: string): number[] {
  const lines = vtt.split(/\n/).filter(l => /-->/.test(l));
  const toSec = (hms: string) => {
    const [hh, mm, rest] = hms.split(':');
    const [ss] = rest.split('.');
    return parseInt(hh) * 3600 + parseInt(mm) * 60 + parseInt(ss);
  };
  const durations: number[] = [];
  for (const l of lines) {
    const m = l.match(/(\d{2}:\d{2}:\d{2}\.\d{3})\s+--\>\s+(\d{2}:\d{2}:\d{2}\.\d{3})/);
    if (m) durations.push(toSec(m[2]) - toSec(m[1]));
  }
  return durations;
}

// Root output dir relative to this test file
const OUTPUT_DIR = path.resolve(__dirname, '../../../output');
const SLIDES_DIR = path.join(OUTPUT_DIR, 'slides');
const VIDEOS_DIR = path.join(OUTPUT_DIR, 'videos');

// Screenshots dir
const ARTIFACTS_DIR = path.resolve(__dirname, '../test-artifacts');


test('complete-daily e2e: HF daily -> slides + video + subtitles (no demo fallback)', async ({ page, context }) => {
  const consoleErrors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      const text = msg.text();
      // Ignore benign Next.js dev hydration warning about extra attributes
      if (/Extra attributes from the server/i.test(text)) return;
      consoleErrors.push(`[console.${msg.type()}] ${text}`);
    }
  });

  const wsMessages: string[] = [];
  context.on('websocket', ws => {
    ws.on('framereceived', e => {
      try {
        const txt = e.text();
        wsMessages.push(txt);
      } catch {}
    });
  });

  // Navigate
  await page.goto('http://localhost:3000/generate');
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'hf-complete-initial.png') });

  // Select complete mode and ensure max_papers=1
  await page.getByRole('button', { name: 'complete' }).click();
  // Start pipeline
  await page.getByRole('button', { name: 'Start Pipeline' }).click();

  // Paper fetching phase
  await test.step('Paper fetching', async () => {
    // Must see that we are fetching HF daily
    await waitForLog(page, 'fetching Hugging Face daily', 60_000);
    // Accept either HF or arXiv fallback, but not demo fallback
    await waitForLog(page, '[papers] source:', 120_000);
    const logs = await getLogs(page);
    expect(logs).toMatch(/\[papers\] source: (huggingface daily|arXiv \(fallback\))/);
    expect(logs).not.toMatch(/falling back to demo/);
  });

  // Content analysis
  let arxivId: string | null = null;
  await test.step('Content analysis + paper event + UI card', async () => {
    await waitForLog(page, '[pipeline] complete: processing 1/', 120_000);
    const logs = await getLogs(page);
    arxivId = extractArxivId(logs);
    expect(arxivId, 'should capture arXiv id from logs').not.toBeNull();
    expect(arxivId!).toMatch(/^\d{4}\.[0-9]{4,5}(?:v\d+)?$/);

    // Prefer WS paper event if available; otherwise rely on UI card
    const hasPaperEvent = wsMessages.some(m => {
      try {
        const obj = JSON.parse(m);
        return obj && obj.type === 'paper' && obj.id && /\d{4}\.[0-9]{4,5}(?:v\d+)?/.test(obj.id);
      } catch { return false; }
    });
    if (!hasPaperEvent) {
      // Fallback: ensure UI card is rendered with arXiv id/link
      const recentCard = page.locator('h2:has-text("Live Logs")').locator('xpath=following::div[contains(@class,"border")]').first();
      await expect(recentCard).toBeVisible();
      await expect(recentCard).toContainText(/\d{4}\.[0-9]{4,5}(?:v\d+)?/);
      await expect(recentCard.getByRole('link', { name: 'arXiv' })).toHaveAttribute('href', /arxiv\.org\/abs\//);
    }

    // Recent paper card contains title, id, authors, and arXiv link
  // Ensure synthesized segment logs and no demo/fallback
  await test.step('TTS segments + no fallback', async () => {
    await waitForLog(page, '[tts] synthesized segment 1/6', 120_000);
    const logs = await getLogs(page);
    expect(logs).not.toMatch(/falling back to demo/i);
    expect(logs).not.toMatch(/LLM produced no sections/i);
    expect(logs).not.toMatch(/fallback simple renderer/i);
  });

    const recentCard = page.locator('h2:has-text("Live Logs")').locator('xpath=following::div[contains(@class,"border")]').first();
    await expect(recentCard).toBeVisible();
    await expect(recentCard).toContainText(/\d{4}\.[0-9]{4,5}(?:v\d+)?/);
    await expect(recentCard.getByRole('link', { name: 'arXiv' })).toHaveAttribute('href', /arxiv\.org\/abs\//);
  });

  // LLM + TTS phase
  await test.step('LLM + TTS integration', async () => {
    await waitForLog(page, '[llm] analyzing paper', 120_000).catch(async () => {
      // Some environments may have slightly different wording
      await waitForLog(page, '[llm] analyzing', 10_000);
    });
    await waitForLog(page, '[llm] script generated', 120_000);
    await waitForLog(page, '[tts] generating speech', 120_000);
  });


  // Script + slides phase
  await test.step('Slides build (6/6)', async () => {
    // Either orchestrator start log or per-slide rendering logs
    const logs = await getLogs(page);
    const orchestratorStart = /\[slides\] orchestrator start/.test(logs);
    if (!orchestratorStart) {
      // fallback: wait briefly for any slide rendering logs
      try { await waitForLog(page, '[slides] rendering', 30_000); } catch {}
    }

    // Wait until 6 thumbnails exist (poll)
    const thumbs = page.locator('img[alt="slide"]');
    await expect.poll(async () => await thumbs.count(), { timeout: 120_000, intervals: [500, 1000, 2000] }).toBe(6);

    // Check each slide image URL loads (>=10KB)
    const count = await thumbs.count();
    for (let i = 0; i < count; i++) {
      const src = await thumbs.nth(i).getAttribute('src');
      expect(src).toBeTruthy();
      const resp = await page.request.get(src!);
      expect(resp.ok()).toBeTruthy();
      const buf = await resp.body();
      expect(buf.length).toBeGreaterThan(10_000);
    }
  });

  // Video + subtitles phase
  await test.step('Video and subtitles', async () => {
    await waitForLog(page, '[video] composing with audio narration', 120_000);

    // Wait for links to appear (video composition may not log the classic ffmpeg message)
    const videoLink = page.getByRole('link', { name: 'Download Video' });
    const vttLink = page.getByRole('link', { name: 'Download Subtitles' });
    await expect(videoLink).toBeVisible({ timeout: 120_000 });
    await expect(vttLink).toBeVisible({ timeout: 120_000 });

    const href = await videoLink.getAttribute('href');
    expect(href).toMatch(new RegExp(`${arxivId!.replace(/\./g, '\\.')}_\\d+\\.mp4`));
    const vhref = await vttLink.getAttribute('href');
    expect(vhref).toMatch(/\.vtt$/);

    // Validate sizes (video > 500KB)
    const vResp = await page.request.get(href!);
    expect(vResp.ok()).toBeTruthy();
    const vBuf = await vResp.body();
    expect(vBuf.length).toBeGreaterThan(500_000);

    const tResp = await page.request.get(vhref!);
    expect(tResp.ok()).toBeTruthy();
    const vtt = await tResp.text();
    expect(vtt).toContain('WEBVTT');
    expect(countVttCues(vtt)).toBe(6);
    const durs = vttDurations(vtt);
    const unique = Array.from(new Set(durs));
    expect(unique.length).toBeGreaterThan(1); // varying durations
  });

  // WS/progress/status
  await test.step('Progress and status', async () => {
    // Status should end at succeeded • 100%
    await expect(page.locator('text=State:')).toContainText('succeeded');
    await expect(page.locator('text=State:')).toContainText('100%');

    // Validate WS JSON structure in captured messages
    const badJson = wsMessages.filter(m => {
      try { JSON.parse(m); return false; } catch { return true; }
    });
    expect(badJson, 'all WS messages parsable JSON').toEqual([]);
  });

  // Ensure no console errors
  expect(consoleErrors, 'no console errors in browser').toEqual([]);

  // Final safety: ensure no demo fallback occurred
  const finalLogs = await getLogs(page);
  expect(finalLogs).not.toMatch(/\[pipeline\] demo BEGIN/);

  // Final screenshot
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'hf-complete-final.png'), fullPage: true });
});

