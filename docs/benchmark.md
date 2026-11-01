# Local benchmark

Measured by `python -m hoico.cli run-all` on the machine that produced this file.
Platform: Linux-6.6.87.2-microsoft-standard-WSL2-x86_64-with-glibc2.36
Python: 3.12.16
CPUs visible to Python: 8

## Stage runtime

- generate: 9.4 seconds
- transform: 212.5 seconds
- load: 80.0 seconds
- dbt: 8.6 seconds
- forecast: 16.9 seconds
- scenarios: 2.7 seconds
- snapshot: 0.2 seconds

## Rows

```json
{
  "bronze_rows": {
    "encounters": 13685,
    "bed_capacity": 22658,
    "staffing": 45313,
    "discharges": 13261,
    "calendar": 2832,
    "operational_events": 48
  },
  "silver_rows": {
    "encounter": 13680,
    "bed_capacity_hourly": 22648,
    "staffing_hourly": 45296,
    "discharge": 13260,
    "operational_event": 48
  },
  "quarantine_rows": {
    "encounter": 4,
    "bed_capacity": 2,
    "staffing": 1,
    "discharge": 1,
    "operational_event": 0
  },
  "duplicates_removed": {
    "encounter": 1,
    "bed_capacity": 8,
    "staffing": 16,
    "discharge": 0,
    "operational_event": 0
  },
  "gold_rows": {
    "fact_arrivals_hourly": 6474,
    "fact_occupancy_hourly": 22648
  }
}
```

This is one synthetic community hospital, about four months of hourly history.
It is not a multi-hospital or production-scale benchmark.
