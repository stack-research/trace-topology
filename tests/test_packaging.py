from __future__ import annotations

import tomllib
from pathlib import Path


def test_core_dependencies_do_not_include_optional_backends(repo_root: Path) -> None:
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = pyproject["project"]["dependencies"]
    optional = pyproject["project"]["optional-dependencies"]

    assert not any(dep.startswith("requests") for dep in dependencies)
    assert any(dep.startswith("requests") for dep in optional["ollama"])
    assert any(dep.startswith("anthropic") for dep in optional["anthropic"])
    assert any(dep.startswith("requests") for dep in optional["all"])
    assert any(dep.startswith("anthropic") for dep in optional["all"])
