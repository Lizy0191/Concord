import os
from pathlib import Path

import pytest
from app.api.main import create_app
from app.bootstrap import build_services
from app.domain.actions import Principal
from app.settings import Settings
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch):
    # Offline regression tests must not inherit a developer's paid providers,
    # server database, credentials, or .env. Explicit integration fixtures use
    # the separate CCA_TEST_* namespace.
    for key in list(os.environ):
        if key.startswith("CCA_") and not key.startswith("CCA_TEST_"):
            monkeypatch.delenv(key)
    from app.settings import Settings

    monkeypatch.setitem(Settings.model_config, "env_file", None)


@pytest.fixture
def admin():
    return Principal(id="test-admin", role="admin")


@pytest.fixture
def services(tmp_path: Path):
    svc = build_services(Settings(data_dir=tmp_path, diagnostic_runtime=True))
    yield svc
    svc.close()


@pytest.fixture
def client(services):
    with TestClient(create_app(services.settings, services)) as client:
        client.headers["Authorization"] = "Bearer local-demo-admin"
        yield client
