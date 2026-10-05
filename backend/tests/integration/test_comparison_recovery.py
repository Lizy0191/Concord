"""A committed comparison outbox survives real DBOS process restart."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.integration
def test_trusted_comparison_recovers_in_real_dbos_process(tmp_path):
    pytest.importorskip("dbos")
    preamble = """
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'backend'))
sys.path.insert(0, str(Path.cwd() / 'backend/tests'))
from app.bootstrap import build_services
from app.settings import Settings
from app.domain.actions import Principal
from test_trusted_comparisons import FixtureExecutor, setup_pair
settings = Settings(data_dir=Path(sys.argv[1]), seed_demo=False, _env_file=None)
executor = FixtureExecutor()
svc = build_services(settings, comparison_executors=(executor,))
admin = Principal(id='recovery-test', role='admin')
"""
    prepare = (
        preamble
        + """
try:
    svc.comparisons.executors.clear()
    project, request, prepared = setup_pair(svc, admin)
    run = svc.comparisons.enqueue(project.id, request, admin)
    with svc.factory.open() as repo:
        job = repo.job(run.id)
        assert len(job.request.revisions) == 2
        assert repo.run(run.id).status == 'QUEUED'
finally:
    svc.close()
"""
    )
    recover = (
        preamble
        + """
try:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        with svc.factory.open() as repo:
            run = next(r for r in repo.runs() if r.category == 'pdf_comparison')
            job = repo.job(run.id)
        if run.status == 'COMPLETED':
            break
        time.sleep(0.05)
    assert run.runtime == 'dbos' and run.status == 'COMPLETED', (run, job)
    assert executor.calls == 1
    assert job.request.engine_version == executor.version
    with svc.factory.open() as repo:
        changes = repo.changes(run.project_id)
        assert len(changes) == 1
        assert changes[0].from_revision_id == job.request.revisions[0].id
        assert changes[0].to_revision_id == job.request.revisions[1].id
        assert changes[0].raw_artifact_key == job.result['artifact_key']
    assert svc.artifacts.read(job.result['artifact_key']) is not None
finally:
    svc.close()
"""
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith("CCA_")}
    for script in (prepare, recover):
        result = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path)],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-4000:]
