#!/usr/bin/env python3
"""Build the paste-ready WordPress block for the FPL projections page.

    component.html  ->  wp_page.html            paste into the post (Custom HTML block)
                    ->  projections_table.html  local dev copy, reads data/ over HTTP

Same wpautop/shortcode safety rules as the usage tool (helpers in
embed_helpers.py, copied from NFLData/ff_utilization/build_embed.py).
Free page: no [s2If] blocks.

Usage:
    python build_embed.py
    python build_embed.py --data-url /wp-content/uploads/f6p-data/fpl_projections.json
"""
import argparse
from pathlib import Path

from embed_helpers import (FETCH, assert_no_line_comments,
                           assert_no_shortcode_brackets, collapse_script_style_blocks)

HERE = Path(__file__).resolve().parent

COMPONENT = HERE / "component.html"
MARKER = "<!-- F6P_FPL:START -->"
DEFAULT_URL = "/wp-content/uploads/f6p-data/fpl_projections.json"


def build(data_source, collapse=True):
    src = COMPONENT.read_text(encoding="utf-8")
    body = src[src.index(MARKER):].replace("__DATA_SOURCE__", data_source)
    assert_no_line_comments(body, "fpl embed")
    assert_no_shortcode_brackets(body, "fpl embed")
    assert "s2If" not in body
    if collapse:
        body = collapse_script_style_blocks(body)
        body = "\n".join(ln for ln in body.splitlines() if ln.strip())
    return body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-url", default=DEFAULT_URL)
    args = ap.parse_args()

    page = HERE / "wp_page.html"
    page.write_text(build(FETCH.format(url=args.data_url)) + "\n", encoding="utf-8")
    print(f"{page.name:<24} {page.stat().st_size/1024:>5.1f} KB   <-- paste this whole file into the post")

    dev = HERE / "projections_table.html"
    dev.write_text(
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>F6P FPL Projections — local dev</title></head>"
        "<body style=\"margin:16px;background:#fff\">\n"
        + build(FETCH.format(url="data/fpl_projections.json"), collapse=False)
        + "\n</body></html>\n", encoding="utf-8")
    print(f"{dev.name:<24} {dev.stat().st_size/1024:>5.1f} KB   (local dev)")
    print(f"\nlive data URL: {args.data_url}")


if __name__ == "__main__":
    main()
