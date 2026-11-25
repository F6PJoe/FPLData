#!/usr/bin/env python3
"""Build data/fpl_projections.json for the projections page.

Pulls FPL Copilot /meta + /predictions (next gameweek through the next
HORIZON gameweeks) and joins FPL's public bootstrap-static for names, teams,
prices and roster %. The API only returns FPL ids -- names always come from
FPL's own feed, joined on fpl_element_id (verified: id 1 = Raya in both).

One row per player per gameweek, columnar like the usage tool:
    {"meta": {...}, "cols": [...], "rows": [[...], ...]}

A double gameweek is summed into one row (nfix = 2); a blank is a row with
nfix = 0 and zeros, so range totals treat it as the zero it is.

Usage:
    python build_data.py
    python build_data.py --horizon 8
"""
import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "https://fplcopilot.com/api/partner/v1"
FPL = "https://fantasy.premierleague.com/api"
DATA = HERE / "data"
RAW = HERE / "raw"

COLS = ["id", "player", "team", "pos", "price", "rost", "gw", "opp", "nfix",
        "xmins", "start", "p60", "xp", "xg", "xa", "cs",
        "app", "gls", "ast", "csp", "gc", "sv", "dc", "bon", "crd"]
# FPL Copilot points-breakdown key -> our column
PTS = {"appearance": "app", "goals": "gls", "assists": "ast", "clean_sheet": "csp",
       "goals_conceded": "gc", "saves": "sv", "defcon": "dc", "bonus": "bon", "cards": "crd"}


def key():
    for line in (HERE / ".env").read_text().splitlines():
        if line.startswith("FPL_COPILOT_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("FPL_COPILOT_KEY missing from fpl_copilot/.env")


def get(url, headers=None, save=None):
    req = urllib.request.Request(url, headers={"User-Agent": "FantasySixPack/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=90) as r:
        body = r.read()
    if save:
        RAW.mkdir(exist_ok=True)
        (RAW / save).write_bytes(body)
    return json.loads(body.decode("utf-8"))


def main(argv=None, meta=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=6, help="gameweeks to include, starting at the next one")
    args = ap.parse_args(argv)

    hk = {"X-Partner-Key": key()}
    if meta is None:
        meta = get(f"{BASE}/meta", hk, "meta.json")["meta"]
    gw0 = meta["next_gw"]
    gw1 = min(gw0 + args.horizon - 1, 38)
    preds = get(f"{BASE}/predictions?gw_from={gw0}&gw_to={gw1}", hk, f"predictions_gw{gw0}-{gw1}.json")
    boot = get(f"{FPL}/bootstrap-static/", save="fpl_bootstrap.json")

    teams = {t["id"]: t["short_name"] for t in boot["teams"]}
    els = {e["id"]: e for e in boot["elements"]}

    rows, missing = [], []
    for p in preds["players"]:
        pid = p["fpl_element_id"]
        e = els.get(pid)
        if not e:
            missing.append(pid)
            continue
        by_gw = {g["gw"]: g for g in p["gws"]}
        player_rows = []
        for gw in range(gw0, gw1 + 1):
            g = by_gw.get(gw) or {"fixtures": [], "xmins": 0, "xpts_total": 0}
            fx = g["fixtures"]
            n = len(fx)
            # The API returns web_name now (checked 2026-11-25: identical to
            # FPL's for all 615 players); FPL's is only a fallback.
            r = dict(id=pid, player=p.get("web_name") or e["web_name"], team=teams[p["team_fpl"]], pos=p["position"],
                     price=e["now_cost"] / 10, rost=float(e["selected_by_percent"]), gw=gw,
                     opp=" ".join(("vs " if f["was_home"] else "@ ") + f["opponent"] for f in fx) or "BLANK",
                     nfix=n, xmins=round(g["xmins"], 1), xp=round(g["xpts_total"], 2))
            r["start"] = round(100 * sum(f["p_start"] for f in fx) / n) if n else 0
            r["p60"] = round(100 * sum(f["p60"] for f in fx) / n) if n else 0
            r["cs"] = round(100 * sum(f["components"]["cs_prob"] for f in fx) / n) if n else 0
            r["xg"] = round(sum(f["components"]["x_goals"] for f in fx), 2)
            r["xa"] = round(sum(f["components"]["xa"] for f in fx), 2)
            for src, col in PTS.items():
                r[col] = round(sum(f["points"].get(src, 0) for f in fx), 2)
            player_rows.append(r)
        # Drop players the model has playing zero minutes in every gameweek
        # of the window -- long-term injured, loans, fourth keepers.
        if any(r["xmins"] >= 1 for r in player_rows):
            rows.extend(player_rows)

    # FPL deadlines (UTC) for every gameweek in the window -- the page shows
    # the selected gameweek's deadline next to the update time.
    deadlines = {str(e["id"]): e["deadline_time"] for e in boot["events"] if gw0 <= e["id"] <= gw1}

    out = {
        "meta": {
            "season": meta["season"], "next_gw": gw0, "gw_from": gw0, "gw_to": gw1,
            "model_version": meta["model_version"], "version": meta.get("default_version"),
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "deadlines": deadlines,
        },
        "cols": COLS,
        "rows": [[r[c] for c in COLS] for r in rows],
    }
    DATA.mkdir(exist_ok=True)
    path = DATA / "fpl_projections.json"
    path.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    nplayers = len({r["id"] for r in rows})
    print(f"{path}  {path.stat().st_size/1024:.0f} KB  GW{gw0}-{gw1}  {nplayers} players  {len(rows)} rows")
    if missing:
        print(f"WARNING: {len(missing)} FPL Copilot ids not in FPL bootstrap (dropped): {missing[:10]}")


if __name__ == "__main__":
    main()
