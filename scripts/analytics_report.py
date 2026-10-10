#!/usr/bin/env python3
"""Print a privacy-safe Cyraduct audience and UTM performance report.

Run from the API repository with the production database configured through
CYRADUCT_DATABASE_URL. The report never prints names, email addresses, or
partnership message contents.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Allow direct execution from the repository root or from this scripts folder.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app import storage


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def count_properties(rows: list[Any], property_name: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        properties = json.loads(row.properties or "{}")
        value = properties.get(property_name)
        if value:
            counts[str(value)] += 1
    return counts


def report(days: int) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff = since.isoformat()
    with storage._engine.begin() as conn:
        events = conn.execute(
            select(storage.analytics_events_table)
            .where(storage.analytics_events_table.c.created_at >= cutoff)
            .order_by(storage.analytics_events_table.c.created_at.asc())
        ).fetchall()
        partners = conn.execute(
            select(storage.partners_table)
            .where(storage.partners_table.c.created_at >= cutoff)
            .order_by(storage.partners_table.c.created_at.asc())
        ).fetchall()

    event_counts = Counter(str(row.event) for row in events)
    audience_routes = count_properties(
        [row for row in events if row.event == "audience_route_click"], "audience"
    )
    destinations = count_properties(
        [row for row in events if row.event == "audience_route_click"], "destination"
    )
    utm_sources = Counter(str(row.utm_source or "direct / unknown") for row in partners)
    utm_campaigns = Counter(str(row.utm_campaign or "none") for row in partners)
    partner_types = Counter(str(row.partner_type) for row in partners)
    submitted_with_campaign = sum(1 for row in partners if row.utm_campaign)
    qualified = len(partners)

    return {
        "window_days": days,
        "since": cutoff,
        "events_total": len(events),
        "event_counts": dict(event_counts.most_common()),
        "audience_routes": dict(audience_routes.most_common()),
        "destinations": dict(destinations.most_common()),
        "partner_submissions": qualified,
        "partner_submissions_with_campaign": submitted_with_campaign,
        "partner_types": dict(partner_types.most_common()),
        "submission_sources": dict(utm_sources.most_common()),
        "submission_campaigns": dict(utm_campaigns.most_common()),
    }


def markdown(data: dict[str, Any]) -> str:
    def bullets(values: dict[str, int]) -> str:
        return "\n".join(f"- **{key}:** {value}" for key, value in values.items()) or "- No data"

    submissions = data["partner_submissions"]
    campaign_submissions = data["partner_submissions_with_campaign"]
    attribution_rate = (campaign_submissions / submissions * 100) if submissions else 0
    return f"""# Cyraduct analytics report

**Window:** last {data['window_days']} days  
**Since:** `{data['since']}`  
**Privacy:** aggregate counts only; no names, email addresses, or message contents are printed.

## Executive summary

- **Tracked events:** {data['events_total']}
- **Partner submissions:** {submissions}
- **Submissions with campaign attribution:** {campaign_submissions} ({attribution_rate:.1f}%)

## Audience route distribution

{bullets(data['audience_routes'])}

## Destination distribution

{bullets(data['destinations'])}

## Event distribution

{bullets(data['event_counts'])}

## Partner types submitted

{bullets(data['partner_types'])}

## Submission sources

{bullets(data['submission_sources'])}

## Submission campaigns

{bullets(data['submission_campaigns'])}

## Weekly interpretation prompts

- Is **Hospitality Finance / AP** generating qualified workflow details, not just clicks?
- Does Finance Guard produce more partner-form starts and submissions than the technical routes?
- Which LinkedIn `utm_content` or campaign produces the strongest written response?
- Are technical visitors reaching API docs, fixtures, public key, or GitHub?
- Did any test or smoke submissions need to be excluded before making a decision?
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7, help="Reporting window in days (default: 7)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Print machine-readable JSON")
    args = parser.parse_args()
    data = report(max(1, min(args.days, 365)))
    print(json.dumps(data, indent=2, sort_keys=True) if args.as_json else markdown(data))


if __name__ == "__main__":
    main()
