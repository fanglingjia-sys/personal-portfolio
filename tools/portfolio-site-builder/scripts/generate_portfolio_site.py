#!/usr/bin/env python3
"""Entrypoint for the portfolio site builder.

Normal build / preview:
  python generate_portfolio_site.py --input-dir <folder> [--serve] [--port 8123]

Management mode (add / remove projects in browser):
  python generate_portfolio_site.py --input-dir <folder> --manage [--port 8123]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from site_builder_core import parse_args, build_site, resolve_output_dir  # noqa: E402


def main() -> int:
    args = parse_args()
    output_dir = build_site(args)
    print(f"Generated site: {output_dir}")

    if getattr(args, "manage", False):
        from manage_server import start_management_server
        input_dir = Path(args.input_dir).expanduser().resolve()
        start_management_server(input_dir, output_dir, args, args.port, args.open_browser)
    elif args.serve:
        from site_builder_core import start_server
        start_server(output_dir, args.port, args.open_browser)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
