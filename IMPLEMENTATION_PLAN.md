# IMPLEMENTATION_PLAN.md — Phase 2 (CBV-managed)

Source of truth: CLAUDE.md Phase 2 Build Order + Definition of Done (10 checks).
Decisions frozen: Email = smtplib (Option A). Weights = remove dead YAML keys (Option A).
Dependency-ordered; do not reorder. Task IDs map to .claude/cbv/o2o_map.md.

- [x] task-001: Fix payback f-string in src/reporting.py so Payback renders a number or Unknown
- [x] task-002: Add load_dotenv() and MIN_SCORE_TO_REPORT env fallback to src/main.py
- [x] task-003: Prune requirements.txt to PyYAML, python-dotenv, psycopg2-binary, pytest
- [x] task-004: Delete stub agents, prompts dir, config sources.yaml, dead YAML keys; inline pipeline in main.py
- [x] task-005: Harden CSV ingest (skip bad rows with warning) and warn on unknown industry
- [x] task-006: Create Supabase Postgres persistence with 2-table migration and listing_url dedup
- [x] task-007: Add smtplib email module and wire post-report send
- [x] task-009: Expand test suite to 9+ tests including 2+ reporting tests
- [x] task-008: Add daily_radar.yml GitHub Actions cron with secrets and prove green dispatch run
- [ ] task-010: Execute all 10 Definition-of-Done checks end-to-end with evidence ledger
