# Databricks notebook source
# Run this on Databricks Free Edition serverless compute after the repo is in the workspace.
# Set HOICO_ROOT to the workspace folder that contains src/ and data/samples.

# COMMAND ----------
dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "hoico")

# COMMAND ----------
import os
import sys
from pathlib import Path

root = Path(os.environ.get("HOICO_ROOT", "/Workspace/Shared/hoico"))
sys.path.insert(0, str(root / "src"))

from hoico.transforms.medallion import run_medallion

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

raw = root / "data" / "samples"
lake = Path("/tmp/hoico-lake")
report = run_medallion(raw, lake)
print(report)

for name in ("encounter", "bed_capacity_hourly", "fact_arrivals_hourly", "fact_occupancy_hourly"):
    layer = "gold" if name.startswith("fact_") else "silver"
    frame = spark.read.parquet(str(lake / layer / name / "parquet"))
    frame.write.format("delta").mode("overwrite").saveAsTable(f"{catalog}.{schema}.{name}")

print("Delta tables written under", f"{catalog}.{schema}")
