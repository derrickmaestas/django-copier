"""Shared test helpers for the dogfood matrix.

Each test file under tests/test_*.py loads one of the answer YAMLs from
tests/answers/, runs `copier.run_copy` into a tmp dir, then exercises
the generated project.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import copier
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ANSWERS_DIR = REPO_ROOT / "tests" / "answers"


def _load_answers(name: str) -> dict:
    return yaml.safe_load((ANSWERS_DIR / f"{name}.yml").read_text())


@pytest.fixture
def generate(tmp_path):
    """Generate a project from the named answer file into tmp_path/<slug>."""

    def _generate(answer_name: str) -> Path:
        data = _load_answers(answer_name)
        dst = tmp_path / data["project_slug"]
        copier.run_copy(
            src_path=str(REPO_ROOT),
            dst_path=str(dst),
            data=data,
            defaults=True,
            unsafe=True,  # required to run _tasks (git init)
            quiet=True,
        )
        return dst

    return _generate


def run(
    cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    """Run a subprocess, fail loudly with stdout/stderr if it errors."""
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=full_env,
        check=True,
        capture_output=True,
        text=True,
    )


def _have(binary: str) -> bool:
    return shutil.which(binary) is not None


# Skip the heavy "uv sync + pytest" steps when uv isn't on the path
# (e.g. unit-test runs of the template repo on a developer machine
# without uv installed). The full dogfood matrix runs in CI where uv
# is always present.
needs_uv = pytest.mark.skipif(not _have("uv"), reason="uv not installed")
