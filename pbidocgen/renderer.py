"""Assemble the consolidated JSON and inject it into template.html."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from .column_usage import build_column_usage
from .source_inventory import build_source_inventory
from .source_queries import build_source_queries
from .source_objects import build_source_objects
from .page_references import attach_report_locations, sync_page_usage, page_feed_rows

TEMPLATE = Path(__file__).parent / "template.html"


def build_payload(model: dict | None, report: dict | None,
                  linked: dict | None, title: str) -> dict:
    mode = ("combined" if model and report
            else "semantic-only" if model
            else "report-only")
    if report:
        attach_report_locations(report)
    columns = build_column_usage(model, report) if model else None
    if model:
        sync_page_usage(model, report, linked, columns)
    if report:
        for page in report["pages"]:
            page["feeds"] = page_feed_rows({"columns": columns, "report": report}, page)
    return {
        "schemaVersion": 2,
        "title": title,
        "mode": mode,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "model": model,
        "report": report,
        "linked": linked,
        "columns": columns,
        "sourceObjects": build_source_objects(model, report, columns),
        "sourceQueries": build_source_queries(model, report),
        "tableSources": build_source_inventory(model, report, linked, columns) if model else [],
    }


def render_html(payload: dict, out_path: str | Path) -> Path:
    template = TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps(payload, ensure_ascii=False)
    # keep the embedded JSON from terminating the script block early
    blob = blob.replace("</", "<\\/")
    html = (template
            .replace("__TITLE__", payload["title"].replace("<", "&lt;"))
            .replace("/*__EXPLORER_CSS__*/", TEMPLATE.with_name("explorer.css").read_text(encoding="utf-8"))
            .replace("/*__EXPLORER_JS__*/", TEMPLATE.with_name("explorer.js").read_text(encoding="utf-8"))
            .replace("/*__DATA__*/null", blob))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
