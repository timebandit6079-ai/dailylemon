#!/usr/bin/env python3
"""
The Daily Lemon — Master Agent
Orchestrates scraping, PDF generation, and site update.
Run: python agent.py
"""

import json
import os
import sys
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

from scrapers import run_all_scrapers
from pdf_gen import generate_daily_lemon_pdf

AEST = ZoneInfo("Australia/Brisbane")


def calculate_stats(leads: list[dict]) -> dict:
    return {
        "total": len(leads),
        "priority_hits": sum(1 for l in leads if l.get("priority")),
        "trade_matches": sum(1 for l in leads if l.get("trade_match")),
        "urgent": sum(1 for l in leads if l.get("urgency", "").startswith("URGENT")),
        "states": sorted({l.get("state", "AU") for l in leads}),
        "by_state": _group_by_state(leads),
    }


def _group_by_state(leads: list[dict]) -> dict:
    groups: dict[str, list] = {}
    for l in leads:
        st = l.get("state", "AU")
        groups.setdefault(st, []).append(l)
    return groups


def build_action_items(leads: list[dict]) -> list[str]:
    """Generate the 'Do These 3 Things' section from live data."""
    items = []
    urgent = [l for l in leads if l.get("urgency", "").startswith("URGENT")]
    trade = [l for l in leads if l.get("trade_match") and not l.get("urgency", "").startswith("URGENT")]

    if urgent:
        l = urgent[0]
        items.append(
            f"URGENT TENDER — {l['title'][:60]} — {l.get('urgency', '')} — {l.get('source','')}"
        )
    if trade:
        l = trade[0]
        items.append(
            f"TRADE MATCH — {l['title'][:60]} — Register on ICN Gateway and submit capability statement"
        )

    items.append(
        "ICN Gateway — Register free (15 min): gateway.icn.org.au — "
        "List: CNC joinery, bulkheads, access floors, NOC fitout, ceilings, partitions"
    )
    return items[:3]


def market_intel_bullets(leads: list[dict]) -> list[str]:
    """Auto-generate market intel from leads."""
    bullets = []
    for l in leads[:6]:
        if l.get("value"):
            bullets.append(
                f"{l['title'][:60]} — {l.get('value','')} | {l.get('status','')} | {l.get('source','')}"
            )
        else:
            bullets.append(
                f"{l['title'][:80]} | {l.get('status','')} — {l.get('source','')}"
            )
    if not bullets:
        bullets.append("No new data centre leads found today — check manually at AusTender, QTenders, EstimateOne.")
    return bullets[:5]


def update_index_html(today: str, pdf_filename: str, stats: dict, leads: list[dict]):
    """Inject today's data into site/index.html via a data.json sidecar."""
    data = {
        "date": today,
        "timestamp": datetime.now(AEST).strftime("%A %d %B %Y — %-I:%M %p AEST"),
        "pdf": f"reports/{pdf_filename}",
        "stats": {
            "leads": stats["total"],
            "priority": stats["priority_hits"],
            "trade": stats["trade_matches"],
            "urgent": stats["urgent"],
        },
        "leads": leads,
        "action_items": build_action_items(leads),
        "market_intel": market_intel_bullets(leads),
        "by_state": {
            state: [
                {k: v for k, v in l.items()} for l in items
            ]
            for state, items in stats["by_state"].items()
        },
        "archive": _build_archive(),
    }

    os.makedirs("site", exist_ok=True)
    with open("site/data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  ✓ site/data.json updated")


def _build_archive() -> list[dict]:
    """List previously generated PDFs as archive entries."""
    archive = []
    reports_dir = "site/reports"
    if not os.path.isdir(reports_dir):
        return archive
    for fname in sorted(os.listdir(reports_dir), reverse=True):
        if fname.endswith(".pdf") and fname.startswith("daily-lemon-"):
            date_part = fname.replace("daily-lemon-", "").replace(".pdf", "")
            archive.append({"date": date_part, "file": f"reports/{fname}"})
    return archive[:30]  # Keep last 30


def main():
    now = datetime.now(AEST)
    today = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%-I:%M %p AEST")

    print(f"\n🍋  The Daily Lemon  ·  {now.strftime('%A %d %B %Y')}  ·  {time_str}")
    print("=" * 60)

    # 1. Scrape
    print("\n[1/4] Scraping sources...")
    leads = run_all_scrapers()

    if not leads:
        print("  ⚠  No leads found — generating empty report.")

    # 2. Stats
    stats = calculate_stats(leads)
    print(f"\n[2/4] Stats: {stats['total']} leads | "
          f"{stats['priority_hits']} priority | "
          f"{stats['trade_matches']} trade matches | "
          f"{stats['urgent']} urgent")

    # 3. Generate PDF
    print("\n[3/4] Generating PDF...")
    os.makedirs("site/reports", exist_ok=True)
    pdf_filename = f"daily-lemon-{today}.pdf"
    pdf_path = os.path.join("site", "reports", pdf_filename)
    generate_daily_lemon_pdf(
        leads=leads,
        stats=stats,
        out_path=pdf_path,
        date_str=now.strftime("%A %d %B %Y"),
        time_str=time_str,
        action_items=build_action_items(leads),
        market_intel=market_intel_bullets(leads),
    )
    print(f"  ✓ {pdf_path}")

    # 4. Update site data
    print("\n[4/4] Updating site data.json...")
    update_index_html(today, pdf_filename, stats, leads)

    print(f"\n✅  Done — {len(leads)} leads → {pdf_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
