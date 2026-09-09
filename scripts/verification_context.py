"""Standalone verification tools must not inherit application credentials or .env.

Use only in single-threaded setup/teardown, never inside the application runtime.
Subprocess-based harnesses instead pass a cleaned child environment explicitly.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def isolated_configuration(directory: Path) -> Iterator[None]:
    previous_directory = Path.cwd()
    previous = {key: value for key, value in os.environ.items() if key.startswith("CCA_")}
    try:
        for key in previous:
            del os.environ[key]
        os.chdir(directory)
        yield
    finally:
        os.chdir(previous_directory)
        for key in list(os.environ):
            if key.startswith("CCA_"):
                del os.environ[key]
        os.environ.update(previous)
