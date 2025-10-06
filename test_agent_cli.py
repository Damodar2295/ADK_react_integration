#!/usr/bin/env python3
"""
Standalone CLI to exercise agent.validate_submission with input parameters.

Examples:
  # Agent + MCP tools (default)
  python test_agent_cli.py --app-id APP001 --control-id C-305377 --au-owner PaymentsTeam \
      --evidence ./samples/esar_export.xlsx ./samples/password_policy.pdf

  # Direct stdio MCP mode (no agent):
  DIRECT_MCP_STDIO=true python test_agent_cli.py --app-id APP001 --control-id C-305377 \
      --au-owner PaymentsTeam --evidence ./samples/esar_export.xlsx
"""

import os
import sys
import json
import argparse
import mimetypes
from typing import List, Dict, Any

from dotenv import load_dotenv

# Ensure project root is importable
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agent import NHAComplianceAgent  # noqa: E402


def _evidence_to_metadata(paths: List[str]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for p in paths:
        if not os.path.isfile(p):
            continue
        ctype, _ = mimetypes.guess_type(p)
        items.append({
            "filename": os.path.basename(p),
            "path": os.path.abspath(p),
            "content_type": ctype or "application/octet-stream",
            "size": os.path.getsize(p),
        })
    return items


def main() -> int:
    load_dotenv(override=True)

    parser = argparse.ArgumentParser(description="Test driver for NHAComplianceAgent")
    parser.add_argument("--app-id", dest="application_id", required=True, help="Application ID")
    parser.add_argument("--control-id", dest="control_id", default="C-305377", help="Control ID (default C-305377)")
    parser.add_argument("--au-owner", dest="au_owner", default=None, help="AU Owner name")
    parser.add_argument("--evidence", nargs="*", default=[], help="Evidence file paths")
    parser.add_argument("--stdio", action="store_true", help="Use direct MCP stdio mode (no agent)")
    args = parser.parse_args()

    if args.stdio:
        os.environ["DIRECT_MCP_STDIO"] = "true"

    evidence = _evidence_to_metadata(args.evidence)

    agent = NHAComplianceAgent()
    result = agent.validate_submission(
        control_id=args.control_id,
        application_id=args.application_id,
        au_owner=args.au_owner,
        evidence_files=evidence,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("success") else 2


if __name__ == "__main__":
    raise SystemExit(main())


