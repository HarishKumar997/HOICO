"""Chronological forecasts. The holdout is not used to choose the model."""

from __future__ import annotations

import json
import logging
import os
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd

from hoico import __version__
from hoico.config import (
    FACILITY_ID,
    HISTORY_END,
    HISTORY_START,
    HOLIDAYS,
    HORIZON_DAYS,
    MODEL_CANDIDATES,
    MODEL_HW,
    MODEL_LGBM,
    MODEL_NAIVE,
    MODEL_TIE_BREAK,
    SERVICE_LINE_IDS,
    SERVICE_LINE_NAMES,
    TRAIN_DAYS,
    VAL_DAYS,
    seed,
)
from hoico.metrics import interval_coverage, little_census, mae, wape

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "lag_1",
    "lag_7",
    "lag_14",
    "roll_mean_7",
    "roll_mean_14",
    "horizon",
    "target_dow",
    "target_month",
    "target_holiday",
    "target_weekend",
    "service_code",
]
FEATURE_VERSION = "lags-1-7-14-roll-7-14-calendar-v1"


def chronological_windows(dates: list[date]) -> dict[str, list[date]]:
    ordered = sorted(dates)
    if ordered != list(dates):
        dates = ordered
    train = dates[:TRAIN_DAYS]
    validation = dates[TRAIN_DAYS : TRAIN_DAYS + VAL_DAYS]
    test = dates[TRAIN_DAYS + VAL_DAYS : TRAIN_DAYS + VAL_DAYS + HORIZON_DAYS]
    if not train or not validation or not test:
        raise ValueError("history is shorter than the 90/14/14 chronological split")
    if train[-1] >= validation[0] or validation[-1] >= test[0]:
        raise ValueError("forecast windows overlap")
    return {"train": train, "validation": validation, "test": test}


def complete_daily(arrivals: pd.DataFrame) -> pd.DataFrame:
    frame = arrivals.copy()
    frame["date"] = pd.to_datetime(frame["census_date"]).dt.date
    grouped = frame.groupby(["service_line", "date"], as_index=False)["arrivals"].sum()
    dates = list(pd.date_range(HISTORY_START, HISTORY_END, freq="D").date)
    rows = []
    for service_line in SERVICE_LINE_IDS:
        part = grouped[grouped["service_line"] == service_line].set_index("date")["arrivals"]
        for current in dates:
            rows.append(
                {
                    "service_line": service_line,
                    "date": current,
                    "arrivals": float(part.get(current, 0.0)),
                }
            )
    return pd.DataFrame(rows)


def _history_until(series: pd.Series, origin: date) -> pd.Series:
    return series.loc[series.index <= origin].astype(float)


def _feature_row(history: pd.Series, origin: date, horizon: int, service_line: str) -> dict[str, Any] | None:
    if len(history) < 14:
        return None
    target_date = origin + timedelta(days=horizon)
    return {
        "service_line": service_line,
        "service_code": SERVICE_LINE_IDS.index(service_line),
        "origin": origin,
        "target_date": target_date,
        "horizon": horizon,
        "lag_1": float(history.iloc[-1]),
        "lag_7": float(history.iloc[-7]),
        "lag_14": float(history.iloc[-14]),
        "roll_mean_7": float(history.iloc[-7:].mean()),
        "roll_mean_14": float(history.iloc[-14:].mean()),
        "target_dow": target_date.weekday(),
        "target_month": target_date.month,
        "target_holiday": int(target_date in HOLIDAYS),
        "target_weekend": int(target_date.weekday() >= 5),
    }


def build_feature_frame(daily: pd.DataFrame, last_date: date) -> pd.DataFrame:
    """Supervised rows whose origin and target are both on or before last_date."""
    rows: list[dict[str, Any]] = []
    for service_line, part in daily.groupby("service_line"):
        series = part.sort_values("date").set_index("date")["arrivals"]
        for origin in series.index:
            if origin > last_date:
                continue
            history = _history_until(series, origin)
            for step in range(1, HORIZON_DAYS + 1):
                target_date = origin + timedelta(days=step)
                if target_date > last_date or target_date not in series.index:
                    continue
                features = _feature_row(history, origin, step, str(service_line))
                if features is None:
                    continue
                features["target"] = float(series.loc[target_date])
                rows.append(features)
    return pd.DataFrame(rows)


def seasonal_naive(history: pd.Series, horizon: int = HORIZON_DAYS, season: int = 7) -> list[float]:
    values = [float(value) for value in history.tolist()]
    if len(values) < season:
        raise ValueError("seasonal naive needs a full week of history")
    preds = []
    for _ in range(horizon):
        nxt = max(0.0, values[-season])
        preds.append(nxt)
        values.append(nxt)
    return preds


def holt_winters(history: pd.Series, horizon: int = HORIZON_DAYS) -> tuple[list[float], bool]:
    import warnings

    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fitted = ExponentialSmoothing(
                history.astype(float).to_numpy(),
                trend="add",
                seasonal="add",
                seasonal_periods=7,
                initialization_method="estimated",
            ).fit(optimized=True, use_brute=False)
        forecast = [max(0.0, float(value)) for value in fitted.forecast(horizon)]
        return forecast, False
    except Exception:
        logger.warning("Holt-Winters fell back to seasonal naive for a series")
        return seasonal_naive(history, horizon), True


def _lgb_params() -> dict[str, Any]:
    return {
        "objective": "regression",
        "metric": "l1",
        "learning_rate": 0.08,
        "num_leaves": 15,
        "min_data_in_leaf": 20,
        "feature_fraction": 1.0,
        "bagging_fraction": 1.0,
        "seed": seed(),
        "deterministic": True,
        "force_row_wise": True,
        "num_threads": 1,
        "verbose": -1,
    }


def fit_lightgbm(features: pd.DataFrame):
    import lightgbm as lgb

    matrix = features[FEATURE_COLUMNS]
    label = features["target"].to_numpy()
    dataset = lgb.Dataset(matrix, label=label)
    return lgb.train(_lgb_params(), dataset, num_boost_round=60)


def _series_map(daily: pd.DataFrame) -> dict[str, pd.Series]:
    mapped = {}
    for service_line, part in daily.groupby("service_line"):
        mapped[str(service_line)] = part.sort_values("date").set_index("date")["arrivals"].astype(float)
    return mapped


def predict_lightgbm(model: Any, daily: pd.DataFrame, origin: date) -> dict[str, list[float]]:
    mapped = _series_map(daily)
    predictions: dict[str, list[float]] = {}
    for service_line in SERVICE_LINE_IDS:
        history = _history_until(mapped[service_line], origin)
        rows = []
        for step in range(1, HORIZON_DAYS + 1):
            feature = _feature_row(history, origin, step, service_line)
            if feature is None:
                raise ValueError(f"not enough history to forecast {service_line}")
            rows.append(feature)
        frame = pd.DataFrame(rows)
        predictions[service_line] = [max(0.0, float(value)) for value in model.predict(frame[FEATURE_COLUMNS])]
    return predictions


def predict_from_origin(daily: pd.DataFrame, origin: date, kind: str, model: Any = None) -> tuple[dict[str, list[float]], int]:
    mapped = _series_map(daily)
    fallbacks = 0
    predictions: dict[str, list[float]] = {}
    if kind == MODEL_LGBM:
        if model is None:
            raise ValueError("lightgbm prediction needs a fitted model")
        return predict_lightgbm(model, daily, origin), 0
    for service_line in SERVICE_LINE_IDS:
        history = _history_until(mapped[service_line], origin)
        if kind == MODEL_NAIVE:
            predictions[service_line] = seasonal_naive(history)
        elif kind == MODEL_HW:
            forecast, fell_back = holt_winters(history)
            predictions[service_line] = forecast
            fallbacks += int(fell_back)
        else:
            raise ValueError(f"unknown model {kind}")
    return predictions, fallbacks


def _score(daily: pd.DataFrame, origin: date, predictions: dict[str, list[float]]) -> list[dict[str, Any]]:
    mapped = _series_map(daily)
    rows = []
    actual_all: list[float] = []
    pred_all: list[float] = []
    for service_line in SERVICE_LINE_IDS:
        for step, predicted in enumerate(predictions[service_line], start=1):
            target_date = origin + timedelta(days=step)
            actual = float(mapped[service_line].loc[target_date])
            rows.append(
                {
                    "service_line": service_line,
                    "horizon_days": step,
                    "target_date": target_date.isoformat(),
                    "actual": actual,
                    "predicted": predicted,
                }
            )
            actual_all.append(actual)
            pred_all.append(predicted)
    actual_arr = np.array(actual_all)
    pred_arr = np.array(pred_all)
    summary = {
        "service_line": "ALL",
        "horizon_days": 0,
        "target_date": "",
        "actual": float(actual_arr.sum()),
        "predicted": float(pred_arr.sum()),
        "mae": mae(actual_arr, pred_arr),
        "wape": wape(actual_arr, pred_arr),
        "n_points": int(actual_arr.size),
    }
    detailed = []
    frame = pd.DataFrame(rows)
    for (service_line, horizon), part in frame.groupby(["service_line", "horizon_days"]):
        detailed.append(
            {
                "service_line": service_line,
                "horizon_days": int(horizon),
                "mae": mae(part["actual"].to_numpy(), part["predicted"].to_numpy()),
                "wape": wape(part["actual"].to_numpy(), part["predicted"].to_numpy()),
                "n_points": int(len(part)),
            }
        )
    return [summary, *detailed, *rows]


def _pooled_wape(score_rows: list[dict[str, Any]]) -> float | None:
    pooled = next(row for row in score_rows if row["service_line"] == "ALL" and row["horizon_days"] == 0)
    return pooled["wape"]


def choose_model(scores: dict[str, float | None]) -> str:
    ranked = []
    for name in MODEL_CANDIDATES:
        value = scores[name]
        if value is None:
            continue
        ranked.append((value, MODEL_TIE_BREAK.index(name), name))
    if not ranked:
        raise ValueError("no model produced a validation WAPE")
    ranked.sort()
    return ranked[0][2]


def _predictions_frame(origin: date, predictions: dict[str, list[float]], lower_q: float, upper_q: float) -> pd.DataFrame:
    rows = []
    for service_line, values in predictions.items():
        for step, predicted in enumerate(values, start=1):
            rows.append(
                {
                    "issue_date": origin.isoformat(),
                    "target_date": (origin + timedelta(days=step)).isoformat(),
                    "facility_id": FACILITY_ID,
                    "service_line": service_line,
                    "horizon_days": step,
                    "yhat": predicted,
                    "yhat_lower": max(0.0, predicted + lower_q),
                    "yhat_upper": max(0.0, predicted + upper_q),
                    "series_kind": "forecast",
                }
            )
    return pd.DataFrame(rows)


def training_los_and_share(encounters: pd.DataFrame, train_end: date) -> tuple[dict[str, float], dict[tuple[str, str], float]]:
    frame = encounters.copy()
    frame["arrival_date"] = pd.to_datetime(frame["arrival_time"], utc=True, errors="coerce").dt.tz_convert(TIMEZONE_NAME()).dt.date
    train = frame[frame["arrival_date"].notna() & (frame["arrival_date"] <= train_end)]
    completed = train[train["encounter_status"] == "completed"].copy()
    completed["los_days"] = (
        pd.to_numeric(completed["departure_epoch"], errors="coerce")
        - pd.to_numeric(completed["arrival_epoch"], errors="coerce")
    ) / 86400
    means = completed.groupby("service_line")["los_days"].mean().to_dict()
    from hoico.config import SERVICE_LINES_BY_ID

    los = {
        service_line: float(means.get(service_line, SERVICE_LINES_BY_ID[service_line].target_los_hours / 24))
        for service_line in SERVICE_LINE_IDS
    }
    eligible = train[train["encounter_status"] != "cancelled"]
    shares: dict[tuple[str, str], float] = {}
    for service_line, part in eligible.groupby("service_line"):
        counts = part.groupby("ward_id").size()
        total = float(counts.sum())
        for ward_id, count in counts.items():
            shares[(str(service_line), str(ward_id))] = float(count) / total if total else 0.0
    return los, shares


def TIMEZONE_NAME() -> str:
    from hoico.config import TIMEZONE

    return TIMEZONE


def project_census(
    predictions: dict[str, list[float]],
    origin: date,
    los_days: dict[str, float],
    shares: dict[tuple[str, str], float],
    wards: list[str],
) -> pd.DataFrame:
    rows = []
    for step in range(1, HORIZON_DAYS + 1):
        target = origin + timedelta(days=step)
        for ward_id in wards:
            census = 0.0
            for service_line in SERVICE_LINE_IDS:
                share = shares.get((service_line, ward_id), 0.0)
                census += little_census(predictions[service_line][step - 1], los_days[service_line] * share)
            # little_census(arrivals * share, los) == arrivals * share * los
            rows.append({"target_date": target.isoformat(), "ward_id": ward_id, "yhat_census": census})
    return pd.DataFrame(rows)


def run_forecast(arrivals: pd.DataFrame, encounters: pd.DataFrame) -> dict[str, Any]:
    daily = complete_daily(arrivals)
    dates = sorted(daily["date"].unique())
    windows = chronological_windows(list(dates))
    train_end = windows["train"][-1]
    val_end = windows["validation"][-1]
    test_origin = val_end

    train_features = build_feature_frame(daily, train_end)
    train_val_features = build_feature_frame(daily, val_end)
    full_features = build_feature_frame(daily, dates[-1])
    lgb_train = fit_lightgbm(train_features)

    validation_scores: dict[str, float | None] = {}
    validation_detail: dict[str, list[dict[str, Any]]] = {}
    fallbacks = {MODEL_HW: 0}
    val_predictions: dict[str, dict[str, list[float]]] = {}
    for kind in (MODEL_NAIVE, MODEL_HW):
        preds, fell_back = predict_from_origin(daily, train_end, kind)
        val_predictions[kind] = preds
        fallbacks[kind] = fell_back
        scored = _score(daily, train_end, preds)
        validation_detail[kind] = scored
        validation_scores[kind] = _pooled_wape(scored)
    val_predictions[MODEL_LGBM] = predict_lightgbm(lgb_train, daily, train_end)
    validation_detail[MODEL_LGBM] = _score(daily, train_end, val_predictions[MODEL_LGBM])
    validation_scores[MODEL_LGBM] = _pooled_wape(validation_detail[MODEL_LGBM])
    selected = choose_model(validation_scores)

    if selected == MODEL_LGBM:
        test_model = fit_lightgbm(train_val_features)
        serving_model = fit_lightgbm(full_features)
    else:
        test_model = None
        serving_model = None

    test_predictions, _ = predict_from_origin(daily, test_origin, selected, test_model)
    test_detail = _score(daily, test_origin, test_predictions)
    baseline_test, _ = predict_from_origin(daily, test_origin, MODEL_NAIVE)
    baseline_detail = _score(daily, test_origin, baseline_test)

    residual_pool = []
    actual_by_key = {
        (row["service_line"], row["horizon_days"]): row["actual"]
        for row in validation_detail[selected]
        if row.get("service_line") != "ALL" and "actual" in row
    }
    for service_line, values in val_predictions[selected].items():
        for step, predicted in enumerate(values, start=1):
            actual = actual_by_key.get((service_line, step))
            if actual is not None:
                residual_pool.append(actual - predicted)
    lower_q = float(np.quantile(residual_pool, 0.10)) if residual_pool else 0.0
    upper_q = float(np.quantile(residual_pool, 0.90)) if residual_pool else 0.0

    test_lower = []
    test_upper = []
    test_actual = []
    for row in test_detail:
        if row["service_line"] == "ALL" or "predicted" not in row:
            continue
        test_actual.append(row["actual"])
        test_lower.append(max(0.0, row["predicted"] + lower_q))
        test_upper.append(max(0.0, row["predicted"] + upper_q))
    coverage = interval_coverage(np.array(test_actual), np.array(test_lower), np.array(test_upper))

    serving_predictions, _ = predict_from_origin(daily, dates[-1], selected, serving_model)
    serving = _predictions_frame(dates[-1], serving_predictions, lower_q, upper_q)
    baseline_serving, _ = predict_from_origin(daily, dates[-1], MODEL_NAIVE)
    serving["baseline_yhat"] = [
        baseline_serving[row.service_line][row.horizon_days - 1] for row in serving.itertuples(index=False)
    ]
    serving["model_name"] = selected
    serving["model_version"] = f"hoico-{__version__}+{selected}+seed{seed()}"

    los_days, shares = training_los_and_share(encounters, train_end)
    from hoico.config import WARD_IDS

    census = project_census(serving_predictions, dates[-1], los_days, shares, list(WARD_IDS))
    test_census = project_census(test_predictions, test_origin, los_days, shares, list(WARD_IDS))

    evaluation_rows = []
    for split_name, detail, origin in (
        ("validation", validation_detail[selected], train_end),
        ("test", test_detail, test_origin),
        ("test_baseline", baseline_detail, test_origin),
    ):
        window = windows["validation"] if split_name == "validation" else windows["test"]
        for row in detail:
            if "mae" not in row:
                continue
            evaluation_rows.append(
                {
                    "model_name": MODEL_NAIVE if split_name == "test_baseline" else selected,
                    "split_name": split_name,
                    "service_line": row["service_line"],
                    "horizon_days": row["horizon_days"],
                    "mae": row["mae"],
                    "wape": row["wape"],
                    "n_points": row["n_points"],
                    "window_start": window[0].isoformat(),
                    "window_end": window[-1].isoformat(),
                    "selected": split_name != "test_baseline" and row["service_line"] == "ALL",
                    "model_version": serving["model_version"].iloc[0],
                    "feature_version": FEATURE_VERSION,
                    "issue_date": origin.isoformat(),
                }
            )
    for kind, score in validation_scores.items():
        evaluation_rows.append(
            {
                "model_name": kind,
                "split_name": "validation_selection",
                "service_line": "ALL",
                "horizon_days": 0,
                "mae": next(row["mae"] for row in validation_detail[kind] if row["service_line"] == "ALL"),
                "wape": score,
                "n_points": next(row["n_points"] for row in validation_detail[kind] if row["service_line"] == "ALL"),
                "window_start": windows["validation"][0].isoformat(),
                "window_end": windows["validation"][-1].isoformat(),
                "selected": kind == selected,
                "model_version": f"hoico-{__version__}+{kind}+seed{seed()}",
                "feature_version": FEATURE_VERSION,
                "issue_date": train_end.isoformat(),
            }
        )

    result = {
        "selected_model": selected,
        "model_version": serving["model_version"].iloc[0],
        "feature_version": FEATURE_VERSION,
        "validation_wape": validation_scores,
        "test_wape": _pooled_wape(test_detail),
        "test_mae": next(row["mae"] for row in test_detail if row["service_line"] == "ALL"),
        "baseline_test_wape": _pooled_wape(baseline_detail),
        "baseline_test_mae": next(row["mae"] for row in baseline_detail if row["service_line"] == "ALL"),
        "interval_coverage": coverage,
        "residual_quantile_10": lower_q,
        "residual_quantile_90": upper_q,
        "holt_winters_fallbacks_on_validation": fallbacks.get(MODEL_HW, 0),
        "windows": {name: [item.isoformat() for item in values] for name, values in windows.items()},
        "daily": daily,
        "serving_arrivals": serving,
        "serving_census": census,
        "test_census": test_census,
        "evaluation_rows": evaluation_rows,
        "los_days": los_days,
        "service_line_names": SERVICE_LINE_NAMES,
    }
    _log_mlflow(result)
    return result


def _log_mlflow(result: dict[str, Any]) -> None:
    import mlflow

    tracking = os.environ.get("MLFLOW_TRACKING_URI", "file:./mlruns")
    mlflow.set_tracking_uri(tracking)
    mlflow.set_experiment("hoico-arrivals")
    with mlflow.start_run(run_name=result["selected_model"]):
        mlflow.log_params(
            {
                "selected_model": result["selected_model"],
                "model_version": result["model_version"],
                "feature_version": result["feature_version"],
                "seed": seed(),
                "train_start": result["windows"]["train"][0],
                "train_end": result["windows"]["train"][-1],
                "validation_start": result["windows"]["validation"][0],
                "validation_end": result["windows"]["validation"][-1],
                "test_start": result["windows"]["test"][0],
                "test_end": result["windows"]["test"][-1],
                "horizon_days": HORIZON_DAYS,
            }
        )
        metrics = {
            "validation_wape_selected": result["validation_wape"][result["selected_model"]],
            "test_wape": result["test_wape"],
            "test_mae": result["test_mae"],
            "baseline_test_wape": result["baseline_test_wape"],
            "baseline_test_mae": result["baseline_test_mae"],
        }
        if result["interval_coverage"] is not None:
            metrics["test_interval_coverage"] = result["interval_coverage"]
        mlflow.log_metrics({key: float(value) for key, value in metrics.items() if value is not None})
        for kind, value in result["validation_wape"].items():
            if value is not None:
                mlflow.log_metric(f"validation_wape_{kind}", float(value))


def write_evaluation_report(result: dict[str, Any], path) -> None:
    coverage = result["interval_coverage"]
    coverage_text = "not computed" if coverage is None else f"{coverage:.1%}"
    lines = [
        "# Forecast evaluation",
        "",
        "Numbers in this file are written by `python -m hoico.cli forecast` from the chronological holdout.",
        "They describe the synthetic Cedarline General series only. They are not a real-world accuracy claim.",
        "",
        f"- Selected model: `{result['selected_model']}`",
        f"- Model version: `{result['model_version']}`",
        f"- Feature version: `{result['feature_version']}`",
        f"- Train window: {result['windows']['train'][0]} to {result['windows']['train'][-1]}",
        f"- Validation window: {result['windows']['validation'][0]} to {result['windows']['validation'][-1]}",
        f"- Test window: {result['windows']['test'][0]} to {result['windows']['test'][-1]}",
        f"- Horizon: {HORIZON_DAYS} days, issued at the last day before each window",
        "",
        "## Validation WAPE used for selection",
        "",
        "| Model | Validation WAPE |",
        "| --- | --- |",
    ]
    for kind in MODEL_CANDIDATES:
        value = result["validation_wape"][kind]
        rendered = "null" if value is None else f"{value:.4f}"
        lines.append(f"| {kind} | {rendered} |")
    lines.extend(
        [
            "",
            "## Untouched test window",
            "",
            f"- Selected model MAE: {result['test_mae']:.3f} arrivals per service-line day",
            f"- Selected model WAPE: {result['test_wape']:.4f}",
            f"- Seasonal-naive MAE: {result['baseline_test_mae']:.3f}",
            f"- Seasonal-naive WAPE: {result['baseline_test_wape']:.4f}",
            f"- Empirical 10/90 residual band coverage on the test points: {coverage_text}",
            "",
            "The band is the validation residual distribution added to the point forecast.",
            "Coverage is reported even when it is far from 80 percent.",
            "",
            "Holt-Winters validation fallbacks to seasonal naive: "
            f"{result['holt_winters_fallbacks_on_validation']}.",
            "",
            "Occupancy uses Little's Law with the mean completed length of stay from the training window only.",
            "Cancelled registrations are excluded. Open encounters are excluded from that average.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    path.with_suffix(".json").write_text(
        json.dumps(
            {
                "selected_model": result["selected_model"],
                "validation_wape": result["validation_wape"],
                "test_wape": result["test_wape"],
                "test_mae": result["test_mae"],
                "baseline_test_wape": result["baseline_test_wape"],
                "baseline_test_mae": result["baseline_test_mae"],
                "interval_coverage": result["interval_coverage"],
                "windows": result["windows"],
                "model_version": result["model_version"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
