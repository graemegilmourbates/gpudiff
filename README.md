# gpudiff · Nightshift Foundry

**Live:** https://gpudiff.com — the GPU Price Changelog: the public record of
change in GPU cloud pricing.

This repo is the shared pipeline behind Nightshift Foundry: a portfolio of
small, agent-run data assets. One dataset in, three surfaces out (site, API, digest), with
validation gates between every step. Humans merge PRs and answer exceptions;
everything else is cron.

Decision memo: https://claude.ai/code/artifact/79446dbf-48dc-43c5-b887-5c9b34e63b9e
Budget: [BUDGET.md](BUDGET.md) — $100 seed, no further investment; the fund
pays for existence, revenue pays for growth.

## Flagship asset #1

**GPU Price Changelog** — the public record of change in GPU cloud pricing:
weekly digest + alerts on top of versioned snapshots. The comparison table is a
supporting surface, not the product. (Competitive scan 2026-08-14: snapshot
sites and private alert tools are crowded; the editorial changelog surface is
unoccupied.)

## Pipeline

```
sources → normalize → validate → data/offers/<date>.json → diff → changelog
                         │                                    │
                    quarantine                          site/ + api/ + digest
```

Principles:

- **Missing beats wrong.** A datum that fails validation is dropped and
  flagged, never published.
- **Quarantine big moves.** A price change over 40% is held for human review
  instead of shipped (`data/quarantine/`).
- **Provenance on every datum.** Each offer carries the URL it was observed at
  and the observation timestamp.
- **Versioned in git.** Snapshots are committed; diffs — the product — come
  free.

## Run it

Zero dependencies beyond Python 3.9+ stdlib.

```bash
# full refresh from live sources (Vast.ai p25 per-GPU, RunPod list prices)
python3 -m pipeline.refresh

# exit nonzero if the last run had a degraded source (CI uses this after committing)
python3 -m pipeline.refresh --check-health

# fixture mode for dev/CI dry runs — writes under data/dev/, never data/
python3 -m pipeline.refresh --date 2026-08-14 --fixtures

# tests
python3 -m unittest discover -s tests
```

`site/` is generated output (gitignored); CI builds and deploys it fresh.

## Workflows

| Workflow      | Trigger            | What it does                                            |
| ------------- | ------------------ | ------------------------------------------------------- |
| `refresh.yml` | hourly cron        | fetch → validate → commit snapshot → build → deploy     |
| `sentinel.yml`| refresh failure    | opens an issue with the failure; the only unscheduled human touchpoint |
| `digest.yml`  | weekly cron        | agent drafts changelog digest as a PR; human label gates sending for the first 90 days |

## Gates (from the memo)

- Day 30: shipped, or the scope gets killed.
- Day 90: ≥1,000 uniques/mo OR ≥150 subscribers OR ≥$50 MRR → keep investing.
- Miss twice → hibernate: cron to weekly, burn to ~$0, next asset enters the
  pipeline.
