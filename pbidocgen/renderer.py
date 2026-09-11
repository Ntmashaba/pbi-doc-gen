"""Assemble the consolidated JSON and inject it into template.html."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from .column_usage import build_column_usage
from .source_inventory import build_source_inventory

TEMPLATE = Path(__file__).parent / "template.html"


def build_payload(model: dict | None, report: dict | None,
                  linked: dict | None, title: str) -> dict:
    mode = ("combined" if model and report
            else "semantic-only" if model
            else "report-only")
    columns = build_column_usage(model, report) if model else None
    if columns and report:
        for measure in model["measures"]:
            measure["usedInReport"] = f"{measure['table']}[{measure['name']}]" in columns["reportMeasures"]
    return {
        "title": title,
        "mode": mode,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "model": model,
        "report": report,
        "linked": linked,
        "columns": columns,
        "tableSources": build_source_inventory(model, report, linked, columns) if model else [],
    }


def render_html(payload: dict, out_path: str | Path) -> Path:
    template = TEMPLATE.read_text(encoding="utf-8")
    blob = json.dumps(payload, ensure_ascii=False)
    # keep the embedded JSON from terminating the script block early
    blob = blob.replace("</", "<\\/")
    html = (template
            .replace("__TITLE__", payload["title"].replace("<", "&lt;"))
            .replace("/*__DATA__*/null", blob))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path
