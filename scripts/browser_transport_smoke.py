# ruff: noqa: E501
"""Execute the production JS API/SSE clients in Chromium against a real Python process.

The harness is explicitly NOT the React UI: a React/Playwright test suite lives in
frontend/e2e and requires the frontend dependencies and build. No model calls occur.
"""

import argparse
import json
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path

from http_smoke import ROOT, Server

BROWSER_EXERCISE = r"""async ({token}) => {
  const {api, setToken, request, requestHeaders, apiUrl, APIError, readSource} = await import('/__contract__/client.js');
  const {readRunEvents} = await import('/__contract__/sse.js');
  const checks = [];
  const check = (value, name) => { if (!value) throw new Error(name); checks.push(name); };
  const wait = async predicate => {
    const deadline = Date.now() + 20000;
    while (Date.now() < deadline) { if (await predicate()) return; await new Promise(resolve => setTimeout(resolve, 50)); }
    throw new Error('Browser timed out waiting for run state');
  };
  setToken('invalid-test-token');
  try { await api.projects(); throw new Error('unauthenticated request succeeded'); }
  catch (error) { check(error instanceof APIError && error.status === 401, 'browser-authentication'); }
  setToken(token);
  await wait(async () => (await api.workspace('harbor-east')).analysis !== null);
  const initial = await api.workspace('harbor-east');
  check(initial.analysis.readiness.every(row => row.status === 'READY'), 'initial-ready');
  const event = {id: crypto.randomUUID(), project_id: 'harbor-east', work_package_id: 'WP-200',
    kind: 'design_revision', title: 'Browser transport V17', change: {revision: 'V17'}};
  const run = await api.events('harbor-east', event);
  await wait(async () => (await api.run(run.id)).status === 'WAITING_APPROVAL');
  const blocked = await api.workspace('harbor-east');
  const proposal = blocked.proposals.find(item => item.work_package_id === 'WP-200');
  check(blocked.analysis.constraints.length > 0 && blocked.analysis.evidence.length > 0, 'blocker-and-bound-evidence');
  check((await api.events('harbor-east', event)).id === run.id, 'idempotent-event-retry');
  try { await api.execute(proposal.id); throw new Error('unapproved execution succeeded'); }
  catch (error) { check(error instanceof APIError && error.status === 403, 'approval-required'); }
  const observed = [];
  const controller = new AbortController();
  const reading = readRunEvents(apiUrl(`/api/runs/${run.id}/events`), {
    headers: requestHeaders(), signal: controller.signal, onEvent: frame => observed.push(frame),
  });
  const approval = await api.approve(proposal.id);
  check((await api.approve(proposal.id)).id === approval.id, 'idempotent-approval-retry');
  await api.execute(proposal.id);
  await wait(async () => (await api.run(run.id)).status === 'COMPLETED');
  await reading;
  check(observed.some(frame => frame.data.type === 'STATE_SNAPSHOT') &&
    observed.some(frame => frame.data.type === 'RUN_FINISHED'), 'authenticated-live-sse');
  check(observed.every((frame, index) => index === 0 || frame.id > observed[index - 1].id), 'monotonic-sse-cursor');
  const receipt = await request(`/api/operations/${proposal.operation_id}`);
  await api.execute(proposal.id);
  check(JSON.stringify(await request(`/api/operations/${proposal.operation_id}`)) === JSON.stringify(receipt), 'stable-execution-receipt');
  const fresh = await api.workspace('harbor-east');
  check(fresh.analysis.snapshot.id !== proposal.snapshot_id && fresh.state.version === receipt.after_version &&
    fresh.analysis.readiness.every(row => row.status === 'READY'), 'fresh-snapshot-recheck');
  const workforce = await api.events('harbor-east', {project_id: 'harbor-east', work_package_id: 'WP-300',
    kind: 'workforce', title: 'Browser crew shortage', change: {available_workers: 1}});
  await wait(async () => (await api.run(workforce.id)).status === 'WAITING_APPROVAL');
  const workforceProposal = (await api.workspace('harbor-east')).proposals.find(item => item.work_package_id === 'WP-300');
  await api.approve(workforceProposal.id); await api.execute(workforceProposal.id);
  await wait(async () => (await api.run(workforce.id)).status === 'COMPLETED');
  check(true, 'secondary-workforce-workflow');
  const text = '# Browser evidence\nChromium transport source alpha.';
  const imported = await api.upload('harbor-east', new File([text], 'browser-evidence.md', {type: 'text/markdown'}));
  await wait(async () => (await api.run(imported.id)).status === 'COMPLETED');
  const job = await api.job(imported.id);
  const chunks = await api.chunks(job.request.document_id);
  check(chunks.length > 0 && chunks.every(chunk => chunk.source_hash === job.request.content_hash), 'document-source-binding');
  check((await api.search('harbor-east', 'Chromium')).length > 0, 'document-full-text-retrieval');
  check(await (await readSource(`/api/documents/${job.request.document_id}/content`)).text() === text, 'authenticated-source-download');
  check((await api.bim('harbor-east')).length > 0, 'structured-bim-contract');
  check((await api.geo('harbor-east')).type === 'FeatureCollection', 'local-gis-contract');
  check(!apiUrl('/api/projects').includes(token), 'credentials-not-in-url');
  const profile = await api.profile();
  document.querySelector('#result').textContent = checks.join('\n');
  return {status: 'PASS', runtime: profile.runtime, checks};
}"""


def exercise(runtime: str, executable: str | None) -> dict:
    from playwright.sync_api import sync_playwright

    work = ROOT / ".verification-work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="browser-", dir=work) as directory:
        folder = Path(directory)
        modules = folder / "modules"
        subprocess.run(
            ["node", str(ROOT / "scripts/transport_modules.mjs"), str(modules)],
            check=True,
            cwd=ROOT,
        )
        token = secrets.token_urlsafe(40)
        server = Server(folder, runtime, token)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    executable_path=executable,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                    headless=True,
                )
                try:
                    page = browser.new_page()
                    page.set_default_timeout(30000)

                    def route_asset(route):
                        name = route.request.url.rsplit("/", 1)[-1]
                        if name in {"client.js", "sse.js"}:
                            route.fulfill(
                                status=200,
                                content_type="text/javascript",
                                body=(modules / name).read_text(),
                            )
                        else:
                            route.fulfill(
                                status=200,
                                content_type="text/html",
                                body=(
                                    "<!doctype html><title>Browser transport "
                                    "contract</title><h1>Production API/SSE client "
                                    "contract</h1><p>This test harness is not the React "
                                    "UI.</p><pre id='result'></pre>"
                                ),
                            )

                    page.route(server.url + "/__contract__/**", route_asset)
                    page.goto(server.url + "/__contract__/index.html")
                    result = page.evaluate(BROWSER_EXERCISE, {"token": token})
                    result["browser"] = browser.version
                    result["scope"] = (
                        "Production API/SSE modules in real Chromium, not React UI rendering"
                    )
                    result["warning"] = (
                        "Diagnostic execution does not prove DBOS durability"
                        if runtime == "diagnostic"
                        else None
                    )
                    return result
                finally:
                    browser.close()
        finally:
            server.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", choices=["dbos", "diagnostic"], default="dbos")
    parser.add_argument("--chromium-executable", default=shutil.which("chromium"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = exercise(args.runtime, args.chromium_executable)
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
