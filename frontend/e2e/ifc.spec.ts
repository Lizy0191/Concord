import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';
import type { Workspace } from '../src/api/client';

const headers = { Authorization: 'Bearer local-demo-admin' };
const project = '/api/projects/harbor-east';
// Fail at test collection, rather than skip, when the real SDK fixture was not generated.
const fixture = fileURLToPath(new URL('../../fixtures/harbor-east.ifc', import.meta.url));
const original = readFileSync(fixture);
const digest = (value: Buffer) => createHash('sha256').update(value).digest('hex');

test('real IFC renders, matches analysis GUIDs, imports, and downloads unchanged', async ({ request, page }) => {
  const errors: string[] = [];
  const remote: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    const url = new URL(request.url());
    if (/^https?:$/.test(url.protocol) && !['127.0.0.1', 'localhost'].includes(url.hostname)) remote.push(url.href);
  });
  const reset = await request.post('/api/demo/reset', { headers });
  expect(reset.status()).toBe(202);
  const resetRun = await reset.json();
  await expect.poll(async () => {
    const response = await request.get(`${project}/workspace`, { headers });
    expect(response.ok()).toBeTruthy();
    const state = await response.json() as Workspace;
    return state.run?.id === resetRun.id && state.run.status === 'COMPLETED' && !state.stale;
  }).toBe(true);
  await page.addInitScript(() => sessionStorage.setItem('cca-token', 'local-demo-admin'));
  await page.goto('/');
  await page.getByRole('button', { name: /Drawing V16.*V17/ }).click();
  const inspector = page.getByRole('complementary', { name: 'Evidence and actions inspector' });
  await expect(inspector.getByText('BLOCKED', { exact: true })).toBeVisible();
  await page.getByRole('navigation', { name: 'Workspace views' }).getByRole('button', { name: 'BIM', exact: true }).click();
  const uploads: string[] = [];
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().includes('/bim/import')) uploads.push(request.url());
  });
  await page.getByLabel('Local IFC file', { exact: true }).setInputFiles(fixture);
  const viewer = page.getByLabel('IFC model viewer', { exact: true });
  await expect(viewer.locator('canvas')).toBeVisible();
  await expect(viewer.getByRole('status')).toContainText(/[1-9]\d*\/[1-9]\d* impact GUIDs matched/);
  expect(uploads).toEqual([]); // Merely opening a local file must never upload it.
  await viewer.getByRole('button', { name: 'Focus', exact: true }).click();
  await expect(viewer.getByRole('button', { name: 'Isolate', exact: true })).toBeEnabled();
  await viewer.getByRole('button', { name: 'Isolate', exact: true }).click();
  await expect(viewer.getByRole('button', { name: 'Show all', exact: true })).toBeEnabled();
  await viewer.getByRole('button', { name: 'Show all', exact: true }).click();
  await expect(viewer.getByRole('button', { name: 'Focus', exact: true })).toBeEnabled();
  await expect(viewer.getByRole('alert')).toHaveCount(0);

  const upload = page.waitForResponse(response => response.request().method() === 'POST'
    && response.url().includes('/bim/import'));
  await page.getByRole('button', { name: 'Import to project', exact: true }).click();
  expect((await upload).status()).toBe(202);
  await expect(page.locator('.bim-workspace').getByRole('status').filter({ hasText: 'Import COMPLETED.' })).toBeVisible();
  expect(uploads).toHaveLength(1);
  const source = await request.get(`${project}/bim/content`, { headers });
  expect(source.status()).toBe(200);
  expect(digest(await source.body())).toBe(digest(original));
  const elements = await request.get(`${project}/bim/elements`, { headers });
  expect(elements.ok()).toBeTruthy();
  expect((await elements.json()).length).toBe(3);
  await page.getByRole('button', { name: 'Structured', exact: true }).click();
  await expect(page.locator('.bim-element')).toHaveCount(3);
  await expect(viewer).toHaveCount(0);
  await page.getByRole('button', { name: 'Open project IFC', exact: true }).click();
  await expect(viewer.getByRole('status')).toContainText('project-import.ifc:');
  await expect(viewer.getByRole('alert')).toHaveCount(0);
  expect(remote).toEqual([]); // WASM and fragment worker must be bundled locally.
  expect(errors).toEqual([]);
});
