from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def samples_dir(repo_root: Path) -> Path:
    return repo_root / "data" / "samples"


@pytest.fixture
def golden_dir(samples_dir: Path) -> Path:
    return samples_dir / "golden"
