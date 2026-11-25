"""Pull a writer-friendly sample from the FPL Copilot partner API.

Fetches /meta, /lineups and /predictions for the next gameweek (+4 more for a
fixture-run view), joins FPL's public bootstrap data for names/teams/prices,
and writes samples/FPL_Copilot_Sample_GW<N>.xlsx.

Key lives in .env (FPL_COPILOT_KEY=...), which is git-ignored.
"""
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HERE = Path(__file__).parent
BASE = "https://fplcopilot.com/api/partner/v1"
FPL = "https://fantasy.premierleague.com/api"
RAW = HERE / "raw"
OUT = HERE / "samples"
RUN_GWS = 5  # next GW + 4


def key():
    for line in (HERE / ".env").read_text().splitlines():
        if line.startswith("FPL_COPILOT_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("FPL_COPILOT_KEY missing from .env")


def get(url, headers=None, save=None):
    req = urllib.request.Request(url, headers={"User-Agent": "FantasySixPack/1.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    if save:
        RAW.mkdir(exist_ok=True)
        (RAW / save).write_bytes(body)
    return json.loads(body.decode("utf-8"))


def main():
    hk = {"X-Partner-Key": key()}
    meta = get(f"{BASE}/meta", hk, "meta.json")["meta"]
    gw = meta["next_gw"]
    last = min(gw + RUN_GWS - 1, 38)
    lineups = get(f"{BASE}/lineups?gw={gw}", hk, f"lineups_gw{gw}.json")
    preds = get(f"{BASE}/predictions?gw_from={gw}&gw_to={last}", hk, f"predictions_gw{gw}-{last}.json")
    boot = get(f"{FPL}/bootstrap-static/", save="fpl_bootstrap.json")

    teams = {t["id"]: t["short_name"] for t in boot["teams"]}
    els = {e["id"]: e for e in boot["elements"]}

    def name(pid):
        e = els.get(pid)
        return e["web_name"] if e else f"#{pid}"

    wb = Workbook()
    hdr_font = Font(bold=True, color="FFFFFF")
    hdr_fill = PatternFill("solid", fgColor="1F4E3D")

    def sheet(ws, headers, rows, widths=None, pct_cols=(), dec_cols=()):
        ws.append(headers)
        for c in ws[1]:
            c.font, c.fill = hdr_font, hdr_fill
            c.alignment = Alignment(horizontal="center", wrap_text=True)
        for r in rows:
            ws.append(r)
        for i, h in enumerate(headers, 1):
            col = get_column_letter(i)
            ws.column_dimensions[col].width = (widths or {}).get(h, max(9, len(h) + 2))
            fmt = "0%" if h in pct_cols else ("0.00" if h in dec_cols else None)
            if fmt:
                for c in ws[col][1:]:
                    c.number_format = fmt
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = ws.dimensions

    # ---- Sheet 1: next-GW projections with breakdown
    rows = []
    for p in preds["players"]:
        g = next((x for x in p["gws"] if x["gw"] == gw), None)
        if not g or not g["fixtures"] or g["xmins"] < 30:
            continue
        e = els.get(p["fpl_element_id"], {})
        fx = g["fixtures"]
        opp = ", ".join(f"{f['opponent']} ({'H' if f['was_home'] else 'A'})" for f in fx)
        pts = {}
        comp = {}
        for f in fx:
            for k, v in f["points"].items():
                pts[k] = pts.get(k, 0) + v
            for k, v in f["components"].items():
                comp[k] = comp.get(k, 0) + v
        f0 = fx[0]
        rows.append([
            name(p["fpl_element_id"]), teams.get(p["team_fpl"]), p["position"],
            e.get("now_cost", 0) / 10, float(e.get("selected_by_percent", 0)) / 100, opp,
            round(g["xmins"], 1), f0["p_start"], f0["p60"], g["xpts_total"],
            round(comp.get("x_goals", 0), 2), round(comp.get("xa", 0), 2), round(comp.get("cs_prob", 0), 2),
            round(pts.get("appearance", 0), 2), round(pts.get("goals", 0), 2), round(pts.get("assists", 0), 2),
            round(pts.get("clean_sheet", 0), 2), round(pts.get("goals_conceded", 0), 2), round(pts.get("saves", 0), 2),
            round(pts.get("defcon", 0), 2), round(pts.get("bonus", 0), 2), round(pts.get("cards", 0), 2),
        ])
    rows.sort(key=lambda r: -r[9])
    ws = wb.active
    ws.title = f"GW{gw} Projections"
    sheet(ws, ["Player", "Team", "Pos", "Price", "Owned", "Opponent", "xMins", "Start %", "60+ %", "xP",
               "xGoals", "xAssists", "Clean Sheet %",
               "Pts: Appear", "Pts: Goals", "Pts: Assists", "Pts: CS", "Pts: GC", "Pts: Saves",
               "Pts: DEFCON", "Pts: Bonus", "Pts: Cards"], rows,
          widths={"Player": 18, "Opponent": 14},
          pct_cols=("Owned", "Start %", "60+ %", "Clean Sheet %"),
          dec_cols=("xP", "xGoals", "xAssists"))
    for c in ws["D"][1:]:
        c.number_format = '"£"0.0"m"'

    # ---- Sheet 2: predicted XIs
    ws = wb.create_sheet(f"GW{gw} Predicted XIs")
    xi_rows = []
    opp_of = {}
    for p in preds["players"]:
        g = next((x for x in p["gws"] if x["gw"] == gw), None)
        if g and g["fixtures"]:
            opp_of.setdefault(p["team_fpl"], ", ".join(
                f"{f['opponent']} ({'H' if f['was_home'] else 'A'})" for f in g["fixtures"]))
    for t in sorted(lineups["teams"], key=lambda t: teams.get(t["team_fpl"], "")):
        by = {"GK": [], "DEF": [], "MID": [], "FWD": []}
        for pl in t["xi"]:
            by[pl["position"]].append(f"{name(pl['fpl_element_id'])} ({pl['p_start']:.0%})")
        xi_rows.append([teams.get(t["team_fpl"]), opp_of.get(t["team_fpl"], ""), t["formation"],
                        "; ".join(by["GK"]), "; ".join(by["DEF"]), "; ".join(by["MID"]), "; ".join(by["FWD"])])
    sheet(ws, ["Team", "Opponent", "Formation", "GK", "Defenders", "Midfielders", "Forwards"], xi_rows,
          widths={"Opponent": 14, "GK": 18, "Defenders": 60, "Midfielders": 70, "Forwards": 40})

    # ---- Sheet 3: fixture run, top 75 by total xP
    gws = list(range(gw, last + 1))
    run = []
    for p in preds["players"]:
        by_gw = {x["gw"]: x for x in p["gws"]}
        vals = [by_gw[g]["xpts_total"] if g in by_gw else 0 for g in gws]
        opps = []
        for g in gws:
            fx = by_gw.get(g, {}).get("fixtures", [])
            opps.append(", ".join(f"{f['opponent']}{'' if f['was_home'] else ' (a)'}" for f in fx) or "BLANK")
        e = els.get(p["fpl_element_id"], {})
        run.append([name(p["fpl_element_id"]), teams.get(p["team_fpl"]), p["position"], e.get("now_cost", 0) / 10]
                   + [x for pair in zip(opps, vals) for x in pair] + [round(sum(vals), 2)])
    run.sort(key=lambda r: -r[-1])
    ws = wb.create_sheet(f"GW{gw}-{last} Run")
    heads = ["Player", "Team", "Pos", "Price"]
    for g in gws:
        heads += [f"GW{g} Opp", f"GW{g} xP"]
    heads.append(f"Total xP GW{gw}-{last}")
    sheet(ws, heads, run[:75], widths={"Player": 18},
          dec_cols=tuple(h for h in heads if "xP" in h))
    for c in ws["D"][1:]:
        c.number_format = '"£"0.0"m"'

    # ---- Sheet 4: read me
    ws = wb.create_sheet("Read Me", 0)
    notes = [
        ("FPL Copilot sample data", True),
        (f"Pulled {datetime.now():%Y-%m-%d %H:%M} from the FPL Copilot partner API. Season {meta['season']}, "
         f"next gameweek GW{gw}. Model {meta['model_version']}.", False),
        ("", False),
        ("CREDIT REQUIRED", True),
        ("Any article, post, newsletter or video using these numbers must mention FPL Copilot with a link on first "
         "use, e.g. \"according to FPL Copilot's expected points\" linking to https://fplcopilot.com/?ref=fantasysixpack", False),
        ("", False),
        ("Tabs", True),
        (f"GW{gw} Projections: every player expected to play 30+ minutes, sorted by expected points (xP).", False),
        (f"GW{gw} Predicted XIs: the model's most likely starting XI for each club, with each player's chance to start.", False),
        (f"GW{gw}-{last} Run: top 75 players by total xP over the next {len(gws)} gameweeks, with opponents ((a) = away).", False),
        ("", False),
        ("Column guide", True),
        ("xMins: expected minutes. Start %: chance he starts. 60+ %: chance he plays 60+ minutes.", False),
        ("xP: expected FPL points for the gameweek. The 'Pts:' columns are the breakdown and add up to xP.", False),
        ("xGoals / xAssists: expected goals (incl. penalties) and assists in this fixture.", False),
        ("Clean Sheet %: team's chance of a clean sheet in the match.", False),
        ("DEFCON: defensive contributions (2 pts at 10 for DEF, 12 for MID/FWD). GC: goals-conceded deductions.", False),
        ("Owned: FPL ownership. Price and ownership come from the official FPL site, not FPL Copilot.", False),
    ]
    for text, bold in notes:
        ws.append([text])
        ws.cell(ws.max_row, 1).font = Font(bold=bold, size=13 if bold else 11)
        ws.cell(ws.max_row, 1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 120

    OUT.mkdir(exist_ok=True)
    path = OUT / f"FPL_Copilot_Sample_GW{gw}.xlsx"
    wb.save(path)
    print(path, "| projections rows:", len(rows), "| XIs:", len(xi_rows), "| run rows:", min(75, len(run)))


if __name__ == "__main__":
    main()
