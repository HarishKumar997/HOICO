"""Command line entry point."""

from __future__ import annotations

import argparse
import logging

from hoico.pipeline import (
    run_all,
    stage_dbt,
    stage_forecast,
    stage_generate,
    stage_load,
    stage_scenarios,
    stage_snapshot,
    stage_transform,
)

COMMANDS = {
    "generate": stage_generate,
    "transform": stage_transform,
    "load": stage_load,
    "dbt": stage_dbt,
    "forecast": stage_forecast,
    "scenarios": stage_scenarios,
    "snapshot": stage_snapshot,
    "run-all": run_all,
}


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="hoico")
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args(argv)
    COMMANDS[args.command]()


if __name__ == "__main__":
    main()
