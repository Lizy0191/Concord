import { randomUUID } from 'node:crypto';
import { expect, test, type APIRequestContext } from '@playwright/test';
import type { Workspace } from '../src/api/client';

const authorization = { Authorization: 'Bearer local-demo-admin' };
const project = '/api/projects/harbor-east';
async function workspace(request: APIRequestContext): Promise<Workspace> {
  const response = await request.get(`${project}/workspace`, { headers: authorization });
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<Workspace>;
}
async function event(request: APIRequestContext, change = { revision: 'V17' }) {
  const response = await request.post(`${project}/events`, { headers: authorization, data: {
    id: randomUUID(), project_id: 'harbor-east', work_package_id: 'WP-200',
    kind: 'design_revision', title: 'Browser E2E design update', change,
  } });
  expect(response.status()).toBe(202);
  return response.json();
}

test.beforeEach(async ({ request, page }) => {
  const reset = await request.post('/api/demo/reset', { headers: authorization });
  expect(reset.status()).toBe(202);
  const resetRun = await reset.json();
  await expect.poll(async () => {
    const current = await workspace(request);
    return current.run?.id === resetRun.id && current.run.status === 'COMPLETED'
      && !current.stale && current.analysis?.readiness.every(row => row.status === 'READY');
  }).toBe(true);
  await page.addInitScript(() => { if (!sessionStorage.getItem('cca-token')) sessionStorage.setItem('cca-token', 'local-demo-admin'); });
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('duct', { ignoreCase: true });
});

test('real browser coordinates design and workforce with approval, receipt, and fresh recheck', async ({ page, request }) => {
  const inspector = page.getByRole('complementary', { name: 'Evidence and actions inspector' });
  await page.getByRole('button', { name: /Drawing V16.*V17/ }).click();
  await expect(inspector.getByText('BLOCKED', { exact: true })).toBeVisible();
  await expect(inspector.getByRole('button', { name: 'Execute & re-check' })).toBeDisabled();
  const before = await workspace(request);
  const proposal = before.proposals.find(item => item.work_package_id === 'WP-200')!;
  expect(before.analysis!.evidence.length).toBeGreaterThan(0);
  const denied = await request.post(`/api/proposals/${proposal.id}/execute`, { headers: authorization });
  expect(denied.status()).toBe(403);
  await inspector.getByRole('button', { name: /^Approve R/ }).click();
  await expect(inspector.getByRole('button', { name: 'Approved' })).toBeVisible();
  await inspector.getByRole('button', { name: 'Execute & re-check' }).click();
  await expect(inspector.getByText('READY', { exact: true })).toBeVisible();
  const after = await workspace(request);
  expect(after.analysis!.snapshot.id).not.toBe(before.analysis!.snapshot.id);
  expect(after.analysis!.snapshot.version).toBe(after.state.version);
  const receipt = await request.get(`/api/operations/${proposal.operation_id}`, { headers: authorization });
  expect(receipt.status()).toBe(200);
  const firstReceipt = await receipt.json();
  await request.post(`/api/proposals/${proposal.id}/execute`, { headers: authorization });
  const retried = await request.get(`/api/operations/${proposal.operation_id}`, { headers: authorization });
  expect(await retried.json()).toEqual(firstReceipt);
  expect((await workspace(request)).state.version).toBe(firstReceipt.after_version);
  await page.getByRole('button', { name: 'Crew shortage' }).click();
  await expect(inspector.getByText('BLOCKED', { exact: true })).toBeVisible();
  await inspector.getByRole('button', { name: /^Approve R/ }).click();
  await inspector.getByRole('button', { name: 'Execute & re-check' }).click();
  await expect(inspector.getByText('READY', { exact: true })).toBeVisible();
});

test('stale approval is rejected and the browser refreshes instead of silently approving', async ({ page, request }) => {
  const inspector = page.getByRole('complementary', { name: 'Evidence and actions inspector' });
  await page.getByRole('button', { name: /Drawing V16.*V17/ }).click();
  await expect(inspector.getByRole('button', { name: /^Approve R/ })).toBeEnabled();
  const staleWorkspace = await workspace(request);
  const old = staleWorkspace.proposals.find(item => item.work_package_id === 'WP-200')!;
  // Keep this tab's old snapshot until the click, while another client updates
  // authoritative facts. This tests the 409 path without a polling-time race.
  const workspaceRoute = '**/api/projects/harbor-east/workspace';
  await page.route(workspaceRoute, route => route.fulfill({ json: staleWorkspace }));
  await event(request, { revision: 'V18' });
  const rejected = page.waitForResponse(response => response.url().endsWith(`/proposals/${old.id}/approve`));
  await inspector.getByRole('button', { name: /^Approve R/ }).click();
  expect((await rejected).status()).toBe(409);
  await page.unroute(workspaceRoute);
  await expect(page.getByRole('alert').first()).toBeVisible();
  expect((await workspace(request)).approvals.some(approval => approval.proposal_id === old.id)).toBe(false);
});

test('inspection R4 requires exact typed confirmation', async ({ page, request }) => {
  const response = await request.post(`${project}/events`, { headers: authorization, data: {
    project_id: 'harbor-east', work_package_id: 'WP-200', kind: 'inspection',
    title: 'Browser E2E inspection', change: { inspection_passed: false },
  } });
  expect(response.status()).toBe(202);
  await page.reload();
  const inspector = page.getByRole('complementary', { name: 'Evidence and actions inspector' });
  const approve = inspector.getByRole('button', { name: 'Approve R4' });
  await expect(approve).toBeDisabled();
  await inspector.getByLabel('R4 confirmation').fill('approve r4');
  await expect(approve).toBeDisabled();
  await inspector.getByLabel('R4 confirmation').fill('APPROVE R4');
  await approve.click();
  await inspector.getByRole('button', { name: 'Execute & re-check' }).click();
  await expect(inspector.getByText('READY', { exact: true })).toBeVisible();
});

test('document upload, retrieval and authenticated source download use the real API', async ({ page }) => {
  await page.getByRole('navigation', { name: 'Workspace views' }).getByRole('button', { name: 'Documents', exact: true }).click();
  await page.locator('input[type=file]').setInputFiles({
    name: 'browser-evidence.md', mimeType: 'text/markdown', buffer: Buffer.from('# Browser evidence\nunique-browser-evidence-phrase'),
  });
  await expect(page.getByText('browser-evidence.md', { exact: true })).toBeVisible();
  await page.getByText('browser-evidence.md', { exact: true }).click();
  await page.getByLabel('Search documents').fill('unique-browser-evidence-phrase');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await expect(page.locator('.document-chunk')).toContainText('unique-browser-evidence-phrase');
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Save selected source' }).click();
  expect((await download).suggestedFilename()).toBe('browser-evidence.md');
});

test('viewer can read but cannot approve or execute', async ({ page, request }) => {
  await event(request);
  await page.evaluate(() => sessionStorage.setItem('cca-token', 'local-demo-viewer'));
  await page.reload();
  const inspector = page.getByRole('complementary', { name: 'Evidence and actions inspector' });
  await expect(inspector.getByText('BLOCKED', { exact: true })).toBeVisible();
  const response = page.waitForResponse(value => value.url().endsWith('/approve'));
  await inspector.getByRole('button', { name: /^Approve R/ }).click();
  expect((await response).status()).toBe(403);
  await expect(page.getByRole('alert').first()).toBeVisible();
  const data = await workspace(request);
  expect(data.approvals).toHaveLength(0);
});

test('structured BIM, capability status, and run history remain usable without optional SDKs', async ({ page }) => {
  const views = page.getByRole('navigation', { name: 'Workspace views' });
  await views.getByRole('button', { name: 'BIM', exact: true }).click();
  await expect(page.locator('.bim-element').first()).toBeVisible();
  await page.locator('.bim-element').first().click();
  await expect(page.locator('.bim-properties')).toBeVisible();
  await views.getByRole('button', { name: 'Capabilities', exact: true }).click();
  await expect(page.getByRole('heading', { name: /capabilit/i }).first()).toBeVisible();
  await views.getByRole('button', { name: 'Operations', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Operations & run history' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Solve schedule' })).toBeDisabled();
});


test('real local GIS renders and selects its linked work package', async ({ page }) => {
  await page.locator('.package-nav').filter({ hasText: 'WP-300' }).click();
  await expect(page.locator('.inspector .mono').first()).toHaveText('WP-300');
  await page.getByRole('navigation', { name: 'Workspace views' }).getByRole('button', { name: 'Site', exact: true }).click();
  await expect(page.getByText('Site map ready', { exact: true })).toBeVisible();
  const canvas = page.locator('.maplibregl-canvas');
  await expect(canvas).toBeVisible();
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  // The original synthetic WP-200 marker is exactly at the map's declared center.
  await canvas.click({ position: { x: box!.width / 2, y: box!.height / 2 } });
  await expect(page.locator('.inspector .mono').first()).toHaveText('WP-200');
  await page.getByRole('navigation', { name: 'Workspace views' }).getByRole('button', { name: 'Work packages', exact: true }).click();
  await expect(page.locator('.maplibregl-canvas')).toHaveCount(0);
});

test('a disconnected event stream reconnects and preserves approvals behind a newer document job', async ({ page, request }) => {
  const inspector = page.getByRole('complementary', { name: 'Evidence and actions inspector' });
  let attempts = 0;
  await page.route('**/api/runs/*/events', route => {
    attempts += 1;
    // Fail the transport, not the backend. The next fetch must reconnect to the
    // real SSE endpoint, rather than receiving a mocked success response.
    return attempts === 1 ? route.abort('connectionreset') : route.continue();
  });
  await page.getByRole('button', { name: /Drawing V16.*V17/ }).click();
  await expect.poll(() => attempts).toBeGreaterThanOrEqual(2);
  await expect(inspector.getByText('BLOCKED', { exact: true })).toBeVisible();
  await expect(inspector.getByRole('button', { name: /^Approve R/ })).toBeEnabled();
  const current = await workspace(request);
  const proposal = current.proposals.find(item => item.work_package_id === 'WP-200')!;
  await page.getByRole('navigation', { name: 'Workspace views' }).getByRole('button', { name: 'Documents', exact: true }).click();
  await page.locator('input[type=file]').setInputFiles({
    name: 'approval-stream.md', mimeType: 'text/markdown', buffer: Buffer.from('Independent document job'),
  });
  await expect(page.getByText('approval-stream.md', { exact: true })).toBeVisible();
  await expect(page.locator('.upload-status')).toContainText('COMPLETED');
  await expect(page.locator('.timeline-heading')).toContainText('COMPLETED');
  const uploaded = await workspace(request);
  expect(uploaded.run!.id).not.toBe(current.run!.id);
  expect(uploaded.analysis_run!.id).toBe(current.analysis_run!.id);
  expect(uploaded.analysis_run!.status).toBe('WAITING_APPROVAL');
  // This separate client does not trigger React Query invalidation in the tab.
  // The approval owner's real stream must remain subscribed even though a newer,
  // completed document job now owns the visible timeline and disables polling.
  const approved = await request.post(`/api/proposals/${proposal.id}/approve`, {
    headers: authorization,
    data: { strong: false, confirmation: '' },
  });
  expect(approved.status()).toBe(200);
  await expect(inspector.getByRole('button', { name: 'Approved', exact: true })).toBeVisible();
  await expect(inspector.getByRole('button', { name: 'Execute & re-check' })).toBeEnabled();
});
