# Vercel Hobby

The Hobby plan is free for personal, non-commercial projects. This console qualifies as a portfolio demo. It serves the aggregate snapshot. It does not run Spark, Postgres, or the scenario solver in Vercel.

1. Generate the snapshot locally so `app/data/public-snapshot.json` has `"status": "ready"`.
2. In Vercel, create a project from this repo with the root directory `app`.
3. Leave `HOICO_DATA_MODE` unset. The server reads the snapshot file.
4. Do not set a secret in the repository. The snapshot has no encounter rows and no passwords.

The scenario sliders use the precomputed grid inside the snapshot. The "local API" button only works when a FastAPI process is reachable, which is the Docker demo, not the public site.

The current Hobby deployment is [https://hoico-cedarline.vercel.app](https://hoico-cedarline.vercel.app).

If the Vercel CLI is already logged in:

```bash
cd app
vercel deploy
```

If it is not logged in, the console still runs locally with `npm run dev` in `app/`.
