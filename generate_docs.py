#!/usr/bin/env python3
"""Generate a self-contained HTML documentation file for a Power BI
semantic model (model.bim), a PBIR report folder, or both together.

Examples
--------
Combined (full lineage and usage analysis):
    python generate_docs.py --model Sales.SemanticModel/model.bim \
                            --report Sales.Report \
                            --output docs/Sales.html --title "Sales"

Semantic model only:
    python generate_docs.py --model model.bim --output docs/model.html

Report only (requirements manifest):
    python generate_docs.py --report Sales.Report --output docs/report.html
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pbidocgen.model_parser import parse_model
from pbidocgen.report_parser import parse_report
from pbidocgen.linker import link
from pbidocgen.renderer import build_payload, render_html


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Power BI documentation generator (semantic model / PBIR report / combined).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--model", help="Path to model.bim (TMSL semantic model)")
    ap.add_argument("--report", help="Path to a PBIR report folder (the *.Report folder)")
    ap.add_argument("--output", "-o", default=None, help="Output HTML path (default: <name>.html)")
    ap.add_argument("--title", default=None, help="Document title (default: derived from inputs)")
    ap.add_argument("--json", dest="json_out", default=None,
                    help="Also write the consolidated analysis JSON to this path")
    ap.add_argument("--word", dest="word_out", default=None,
                    help="Also write a Word document (.docx) to this path — the narrative "
                         "subset for handovers and sign-off; the HTML stays the working doc")
    ap.add_argument("--agent", dest="agent_out", nargs="?", const="", default=None,
                    metavar="PATH",
                    help="Also write an agent context document (.agent.md) — the compact "
                         "markdown distillation for LLM agents. With no PATH, writes next "
                         "to the HTML output")
    args = ap.parse_args(argv)

    if not args.model and not args.report:
        ap.error("Provide --model, --report, or both.")

    model = report = linked = None

    if args.model:
        bim = Path(args.model)
        if not bim.exists():
            print(f"error: model file not found: {bim}", file=sys.stderr)
            return 2
        print(f"Parsing semantic model  {bim}")
        model = parse_model(bim)
        print(f"  {len(model['tables'])} tables, {len(model['measures'])} measures, "
              f"{len(model['relationships'])} relationships")

    if args.report:
        rep = Path(args.report)
        if not rep.exists():
            print(f"error: report folder not found: {rep}", file=sys.stderr)
            return 2
        print(f"Parsing report folder   {rep}")
        report = parse_report(rep)
        n_vis = sum(len(p["visuals"]) for p in report["pages"])
        print(f"  {len(report['pages'])} pages, {n_vis} visuals, "
              f"{len(report['manifest'])} distinct field references")

    if model and report:
        print("Linking report to model")
        linked = link(model, report)
        verdicts = {}
        for u in linked["tableUsage"]:
            verdicts[u["usage"]] = verdicts.get(u["usage"], 0) + 1
        print("  usage verdicts: " + ", ".join(f"{k}={v}" for k, v in sorted(verdicts.items())))
        broken = [w for w in linked["warnings"] if w["category"] == "Broken binding"]
        if broken:
            print(f"  ⚠ {len(broken)} broken binding(s) — see the Warnings tab")

    title = args.title or (model["name"] if model else report["name"])
    payload = build_payload(model, report, linked, title)

    out = args.output or f"{title}.html"
    path = render_html(payload, out)
    print(f"Wrote {path}  ({path.stat().st_size/1024:.0f} KB, mode: {payload['mode']})")

    if args.json_out:
        jp = Path(args.json_out)
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {jp}")

    if args.word_out:
        from pbidocgen.word_writer import render_docx
        wp = render_docx(payload, args.word_out)
        print(f"Wrote {wp}  ({wp.stat().st_size/1024:.0f} KB, Word)")

    if args.agent_out is not None:
        from pbidocgen.agent_writer import render_agent_md, estimate_tokens
        apath = Path(args.agent_out) if args.agent_out else path.with_suffix(".agent.md")
        ap_ = render_agent_md(payload, apath)
        print(f"Wrote {ap_}  ({ap_.stat().st_size/1024:.0f} KB, "
              f"~{estimate_tokens(ap_.read_text(encoding='utf-8')):,} tokens, agent context)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
