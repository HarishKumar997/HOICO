# Model card

## Intended use

Planning estimates of daily eligible arrivals by service line for the next 14 days, and a derived average census by ward. A person compares scenarios. The model does not assign patients, set triage, or recommend treatment.

## Data

Synthetic Cedarline General history from 5 March 2026 through 30 June 2026. Cancelled registrations are excluded from the target. The series is built from weekday, weekend, and holiday factors plus Poisson noise. It is not a sample from a hospital.

## Models

1. Seasonal naive: the value from seven days earlier, rolled forward for horizons beyond one week.
2. Holt-Winters additive trend and weekly seasonality, fit per service line. A failed fit falls back to seasonal naive and the fallback is counted.
3. LightGBM regression with lags 1, 7, and 14, trailing means of 7 and 14 days, horizon, and calendar fields of the target date. Target encoding is a fixed service-line index. Trees: 60. One thread and a fixed seed.

Features at an origin use only arrivals on or before that origin. The validation window is not used to fit the selection models. The test window is scored once, after selection. If validation WAPE ties, the simpler model wins: seasonal naive, then Holt-Winters, then LightGBM.

The served forecast is refit through 30 June 2026 only after the test metrics are stored. Those test metrics describe the holdout, not the forward July forecast.

Prediction bands are the 10th and 90th percentiles of validation residuals, added to the point forecast and clipped at zero. Coverage on the test points is reported even when it is poor.

## Occupancy

Mean completed length of stay and ward shares are fit on training arrivals only. Open stays do not enter the mean.

## Limits

Small single-origin backtests. Synthetic seasonality can make a seasonal model look strong. Do not quote the WAPE as a real-world error. No protected characteristic is an input.
