import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import assert from 'node:assert/strict';

const root = fileURLToPath(new URL('..', import.meta.url));

function read(path) {
  return readFileSync(join(root, path), 'utf8');
}

test('workflow API client uses the agreed backend contract paths', () => {
  const generationApi = read('src/api/generation.ts');
  const htmlApi = read('src/api/html.ts');

  [
    '/api/templates',
    '/api/campaigns',
    '/plan/generate',
    '/plan/approve',
    '/images/batches',
    '/api/image-batches/',
    '/images/select',
    '/html/generate',
  ].forEach((path) => {
    assert.match(generationApi, new RegExp(path.replaceAll('/', '\\/')));
  });

  assert.match(htmlApi, /\/api\/html\/\$\{versionId\}/);
  assert.match(htmlApi, /\/preview`/);
  assert.match(htmlApi, /\/versions`/);
});

test('candidate grid exposes completed and failed slot states', () => {
  const card = read('src/components/CandidateGrid/CandidateCard.tsx');

  assert.match(card, /item\.status === 'completed'/);
  assert.match(card, /item\.status === 'failed'/);
  assert.match(card, /candidate-card__progress-fill/);
  assert.match(card, /生成失败/);
  assert.match(card, /选为底图/);
});

test('HTML preview iframe keeps scripts disabled', () => {
  const preview = read('src/components/HtmlPreview/HtmlPreview.tsx');

  assert.match(preview, /sandbox="allow-same-origin"/);
  assert.doesNotMatch(preview, /allow-scripts/);
});

test('core workflow pages expose acceptance actions', () => {
  const brief = read('src/pages/BriefPage.tsx');
  const plan = read('src/pages/PlanReviewPage.tsx');
  const imageBatch = read('src/pages/ImageBatchPage.tsx');
  const htmlGenerate = read('src/pages/HtmlGeneratePage.tsx');
  const htmlEditor = read('src/pages/HtmlEditorPage.tsx');

  assert.match(brief, /生成视觉方案/);
  assert.match(plan, /确认方案，进入底图生成/);
  assert.match(imageBatch, /重新生成一批/);
  assert.match(imageBatch, /以此底图生成 HTML/);
  assert.match(htmlGenerate, /生成 HTML 海报/);
  assert.match(htmlEditor, /保存为新版本/);
  assert.match(htmlEditor, /版本历史/);
});
