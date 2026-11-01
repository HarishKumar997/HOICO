"""Spark medallion check. Skipped when the machine has no JVM."""

import shutil
from datetime import timedelta

import pytest

from hoico.config import HISTORY_START
from hoico.generate.synthetic import generate, write_bundle
from hoico.transforms.medallion import run_medallion

pytestmark = pytest.mark.spark


@pytest.mark.skipif(shutil.which("java") is None, reason="Spark needs a local JVM")
def test_medallion_overwrite_is_idempotent(tmp_path):
    raw = tmp_path / "raw"
    lake = tmp_path / "lake"
    bundle = generate(start=HISTORY_START, end=HISTORY_START + timedelta(days=2), seed=42)
    write_bundle(bundle, raw)
    first = run_medallion(raw, lake)
    second = run_medallion(raw, lake)
    assert first["silver_rows"]["encounter"] == second["silver_rows"]["encounter"]
    assert second["silver_rows"]["encounter"] < second["bronze_rows"]["encounters"]
    assert second["duplicates_removed"]["encounter"] >= 1
    assert second["quarantine_rows"]["encounter"] >= 4
