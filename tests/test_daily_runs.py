from datetime import date

from src.daily_runs import folder_name, write_daily_run


def test_folder_name_matches_convention():
    assert folder_name(date(2026, 7, 4)) == "7.4.2026"
    assert folder_name(date(2026, 12, 25)) == "12.25.2026"


def test_writes_dated_folder_when_businesses_found(tmp_path):
    path = write_daily_run("# report", found_count=3, base_dir=tmp_path, day=date(2026, 7, 5))
    assert path is not None
    assert path == tmp_path / "Daily Runs" / "7.5.2026" / "daily_report.md"
    assert path.read_text(encoding="utf-8") == "# report"


def test_skips_when_nothing_found(tmp_path):
    path = write_daily_run("# report", found_count=0, base_dir=tmp_path, day=date(2026, 7, 5))
    assert path is None
    assert not (tmp_path / "Daily Runs").exists()
