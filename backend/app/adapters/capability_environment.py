"""Installed-package and credential inspection; never performs a paid/service request."""

import importlib.metadata
import importlib.util
import os

from app.domain.runs import Capability


def dependency(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def optional(
    name: str,
    implementation: str,
    module: str,
    enabled: bool,
    credential: bool | None = None,
    reason: str = "Configured; service use is not live-probed",
    distribution: str | None = None,
) -> Capability:
    available = dependency(module)
    if not available:
        status, reason = (
            "unavailable_dependency",
            f"Install the optional dependency for {implementation}",
        )
    elif enabled and credential is False:
        status, reason = (
            "unavailable_credential",
            "Required credential or explicit model configuration is missing",
        )
    else:
        status = "enabled" if enabled else "available_disabled"
        if not enabled:
            reason = "Implementation available; not selected in this profile"
    try:
        version = importlib.metadata.version(distribution or module)
    except importlib.metadata.PackageNotFoundError:
        version = None
    return Capability(
        name=name,
        implementation=implementation,
        status=status,
        enabled=enabled,
        dependency_available=available,
        credential_present=credential,
        service_reachable=None,
        reason=reason,
        version=version,
    )


def model_credential(identifier: str, key: str) -> bool | None:
    if not identifier:
        return False
    prefix = identifier.split(":", 1)[0]
    if prefix in {"openai", "openai-chat", "openai-responses"}:
        return bool(key)
    variable = {
        "anthropic": "ANTHROPIC_API_KEY",
        "google-gla": "GOOGLE_API_KEY",
        "google": "GOOGLE_API_KEY",
    }.get(prefix)
    # Workload identity/custom providers cannot be verified by checking a generic key.
    return bool(os.environ.get(variable)) if variable else None


def fixed(name: str, implementation: str, reason: str, *, enabled: bool = True) -> Capability:
    return Capability(
        name=name,
        implementation=implementation,
        status="enabled" if enabled else "available_disabled",
        enabled=enabled,
        dependency_available=True,
        reason=reason,
    )
