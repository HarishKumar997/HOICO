"""Deduplication. Latest source_updated_at wins; source_row_number breaks ties."""

from __future__ import annotations

import pandas as pd


def deduplicate(
    frame: pd.DataFrame,
    keys: list[str],
    order_col: str = "source_updated_at",
) -> tuple[pd.DataFrame, int]:
    if frame.empty:
        return frame.copy(), 0
    before = len(frame)
    sort_cols = [order_col]
    ascending = [False]
    if "source_row_number" in frame.columns:
        sort_cols.append("source_row_number")
        ascending.append(False)
    ordered = frame.sort_values(sort_cols, ascending=ascending, kind="mergesort")
    kept = ordered.drop_duplicates(keys, keep="first").copy()
    removed = before - len(kept)
    return kept, removed
