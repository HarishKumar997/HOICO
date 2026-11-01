# Databricks Free Edition

Free Edition is a no-cost, non-commercial workspace. It does not need a credit card or a cloud-provider account. It is serverless, Python-only for this project, and it pauses compute after the daily fair-use quota. Do not upload real patient data. The sample files in `data/samples` are synthetic.

This path is optional. The local Docker pipeline does not need it.

## One notebook run

1. Sign up at the Databricks Free Edition page. Do not start the commercial trial that attaches AWS, Azure, or GCP.
2. In the workspace, add this repository as a Git folder, or upload `src/` and `data/samples/`.
3. Open `infra/databricks/notebooks/medallion.py`.
4. Set the environment or widget path `HOICO_ROOT` to that folder.
5. Set the catalog widget to the catalog you see in Catalog Explorer. `main` is only the default.
6. Attach serverless compute and run the notebook.

The notebook calls `hoico.transforms.medallion.run_medallion` and writes Delta tables for encounters, capacity, hourly arrivals, and hourly occupancy. Forecasting stays in the local stack so the free-tier job remains one task.

## Bundle

From `infra/databricks`, with the Databricks CLI already logged in:

```bash
databricks bundle deploy -t free --var="workspace_host=https://YOUR-WORKSPACE" --var="catalog=YOUR-CATALOG"
databricks bundle run hoico_medallion -t free --var="workspace_host=https://YOUR-WORKSPACE"
```

If the CLI is not authenticated, stop there. Do not create a paid workspace to finish the demo.
