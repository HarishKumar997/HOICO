import fs from "fs";
import path from "path";

import type { Dashboard } from "./types";

export async function loadDashboard(): Promise<Dashboard> {
  const override = process.env.HOICO_SNAPSHOT_PATH;
  const filePath =
    override && fs.existsSync(override)
      ? override
      : path.join(process.cwd(), "data", "public-snapshot.json");
  const raw = fs.readFileSync(filePath, "utf8");
  return JSON.parse(raw) as Dashboard;
}
