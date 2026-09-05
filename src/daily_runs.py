from __future__ import annotations

"""Per-day run archive.

Each day the engine runs and actually finds businesses, drop a dated folder
under `Daily Runs/` and save that day's report inside it. Folder names match
the existing convention (`M.D.YYYY`, no zero-padding, e.g. `7.4.2026`).
"""

import logging
from datetime import date
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DAILY_RUNS_DIR = "Daily Runs"


def folder_name(day: date) -> str:
    return f"{day.month}.{day.day}.{day.year}"


def write_daily_run(
    report_markdown: str,
    found_count: int,
    base_dir: str | Path = ".",
    day: Optional[date] = None,
    filename: str = "daily_report.md",
) -> Optional[Path]:
    """Archive today's report in a dated folder, but only if businesses were found.

    Returns the path written, or None when nothing was found (no empty folders).
    """
    if found_count <= 0:
        logger.info("No businesses found today; skipping Daily Runs archive.")
        return None

    day = day or date.today()
    run_dir = Path(base_dir) / DAILY_RUNS_DIR / folder_name(day)
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / filename
    out_path.write_text(report_markdown, encoding="utf-8")
    logger.info("Archived daily run to %s", out_path)
    return out_path
