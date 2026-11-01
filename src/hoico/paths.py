"""Repository paths. HOICO_ROOT overrides discovery so Docker and tests agree."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    override = os.environ.get("HOICO_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    path = repo_root() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def generated_dir() -> Path:
    path = data_dir() / "generated"
    path.mkdir(parents=True, exist_ok=True)
    return path


def raw_dir() -> Path:
    path = generated_dir() / "raw"
    path.mkdir(parents=True, exist_ok=True)
    return path


def lake_dir() -> Path:
    path = data_dir() / "lake"
    path.mkdir(parents=True, exist_ok=True)
    return path


def sample_dir() -> Path:
    path = data_dir() / "samples"
    path.mkdir(parents=True, exist_ok=True)
    return path


def snapshot_path() -> Path:
    path = repo_root() / "app" / "data" / "public-snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def docs_dir() -> Path:
    path = repo_root() / "docs"
    path.mkdir(parents=True, exist_ok=True)
    return path
