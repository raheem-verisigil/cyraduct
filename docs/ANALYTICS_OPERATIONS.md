# Internal analytics operations

The public API accepts privacy-limited engagement events at `POST /api/analytics/events`. It stores only allowlisted event names and bounded properties; it does not store IP addresses or raw form content in the analytics table.

## Run a seven-day report

```bash
cd /path/to/cyraduct
python scripts/analytics_report.py --days 7
```

The script reads `CYRADUCT_DATABASE_URL`, prints aggregate counts, and never prints partner names, emails, or messages.

## JSON output

```bash
python scripts/analytics_report.py --days 7 --json
```

Use JSON output for a future internal dashboard or scheduled report. No public analytics summary endpoint is exposed by design.

## Interpretation

Use the weekly checklist at [`/home/ubuntu/cyraduct-weekly-analytics-review.md`](../../cyraduct-weekly-analytics-review.md). Treat qualified workflow descriptions and referrals as stronger evidence than page views or event volume.

## Production follow-up

Before high-volume traffic, add retention/aggregation policy for `analytics_events` and a private operator authentication layer if a hosted dashboard is introduced. Do not expose raw partner submissions or event properties publicly.
