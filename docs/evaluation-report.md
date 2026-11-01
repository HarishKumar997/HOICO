# Forecast evaluation

Numbers in this file are written by `python -m hoico.cli forecast` from the chronological holdout.
They describe the synthetic Cedarline General series only. They are not a real-world accuracy claim.

- Selected model: `holt_winters`
- Model version: `hoico-1.0.0+holt_winters+seed42`
- Feature version: `lags-1-7-14-roll-7-14-calendar-v1`
- Train window: 2026-03-05 to 2026-06-02
- Validation window: 2026-06-03 to 2026-06-16
- Test window: 2026-06-17 to 2026-06-30
- Horizon: 14 days, issued at the last day before each window

## Validation WAPE used for selection

| Model | Validation WAPE |
| --- | --- |
| seasonal_naive | 0.2425 |
| holt_winters | 0.1707 |
| lightgbm | 0.1792 |

## Untouched test window

- Selected model MAE: 3.302 arrivals per service-line day
- Selected model WAPE: 0.1709
- Seasonal-naive MAE: 4.893
- Seasonal-naive WAPE: 0.2532
- Empirical 10/90 residual band coverage on the test points: 83.3%

The band is the validation residual distribution added to the point forecast.
Coverage is reported even when it is far from 80 percent.

Holt-Winters validation fallbacks to seasonal naive: 0.

Occupancy uses Little's Law with the mean completed length of stay from the training window only.
Cancelled registrations are excluded. Open encounters are excluded from that average.
