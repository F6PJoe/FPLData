# FPL Copilot projections (Fantasy Premier League)

Free projections page on fantasysixpack built from the FPL Copilot partner
API (fplcopilot.com). Started 2026-11-05.

**Own repo (since 2026-11-25): `F6PJoe/FPLData`, public** -- scripts only, same
split as NFLData: the code is public, nothing sensitive is in it (API key and
SFTP login are GitHub secrets / a git-ignored `.env`), and the data it
produces goes straight to the site, not into the repo. Local copy:
`Documents\FPLData`. It was first built inside the NFLData repo as
`fpl_copilot/` and moved out; nothing here depends on NFLData any more (the
SFTP and WordPress-safety helpers were copied in as `sftp_helpers.py` /
`embed_helpers.py`). GitHub secrets are per-repo, so the workflow's secrets
live in THIS repo, not NFLData's.

**Public-repo rules:** run logs are public, so never print the server path,
host, key, or API key in script output. Keep partner contact details and
partnership terms out of this file; they live in Joe's own notes.

## API
- Base `https://fplcopilot.com/api/partner/v1`, header `X-Partner-Key`.
  Key lives in `.env` (`FPL_COPILOT_KEY=`, plus the `SFTP_*` login), git-ignored.
- `/meta` (next_gw, version), `/predictions?gw_from=&gw_to=`, `/lineups?gw=`,
  `/players/{id}`. 60 req/min, 20k/day.
- **Names:** `/predictions` and `/players/{id}` now return `web_name`,
  `first_name`, `second_name` (added after launch; identical to FPL's names for
  all 615 players, checked 2026-11-25). `/lineups` still returns ids only.
  **Team short names, price and roster %** still come from FPL's public
  `bootstrap-static`, joined on `fpl_element_id` / `team_fpl`.
- `/meta.generated_at` looked stale (2026-09-01) while `next_gw` and
  `default_version` were current. Treat `default_version` as the change signal.

## Credit (partnership condition)
Every page showing the numbers carries the "Prediction data powered by FPL
Copilot" banner linking `https://fplcopilot.com/?ref=fantasysixpack`. It's
built into `component.html` -- don't remove it. Writers mention FPL Copilot
with a link on first use. The banner's tooltip was edited to drop "your team
is loaded" (no team_id on this page).

## The projections page
```
build_data.py    -> data/fpl_projections.json   (next 6 GWs, one row per player-GW)
component.html   <- the ONLY file to edit for the page
build_embed.py   -> wp_page.html                paste into a Custom HTML block
                 -> projections_table.html      local dev copy (preview server "fpl-projections")
upload.py        -> wp-content/uploads/f6p-data/fpl_projections.json (public; page is free)
```
Same build rules as the NFLData usage tool (`embed_helpers.py` is a copy of
its helpers -- if a fix lands there, copy it here):
no `//` comments in the script, no innerHTML, no shortcode-like brackets,
style/script collapsed to one line for wpautop.

- Joe asked for **Rost%** instead of "ownership" (it's FPL's selected_by_percent).
- Views: Gameweek (one GW) and Range (sums GWs; Total / Per GW toggle).
  Start%/60+%/CS% average over fixtures played; blanks count as 0 in Per GW.
- Players with <1 expected minute in every GW of the window are dropped.

## Refresh
FPL deadlines move around (Sat 11:00 UK one week, Tue 18:30 the next), so
the refresh doesn't follow a calendar. `refresh.py` checks `/meta` and only
rebuilds + uploads when `default_version` or `next_gw` changed; `--force`
rebuilds anyway (daily, for FPL's overnight price/Rost% changes). Logs to
`refresh.log`. The page only needs re-pasting when component.html changes.

**Automation: `.github/workflows/fpl_projections_refresh.yml`** (written
2026-11-25). Driven by cron-job.org via workflow_dispatch (no native
`schedule:`, like the other workflows): job 1 every 2 hours (check only),
job 2 daily 07:05 UTC with input `force=true`. A no-change run uploads
nothing, so overlapping runs are harmless (there's also a `concurrency` group). Needs one NEW repo secret, `FPL_COPILOT_KEY`; the SFTP
secrets already exist (shared with the usage tool). refresh.py compares
against the file LIVE on the site (browser UA -- the site 403s default
script UAs), not a local copy, since a runner has none.
FPL Copilot's version changed 3 times between 10:47 and 15:28 ET on
2026-11-25, so a 2-hour check is not overkill.
**Unverified from a GitHub runner:** FPL's own `bootstrap-static` (names no
longer need it, but team names/price/Rost% do) may block datacenter IPs --
run it once from the Actions tab and read the log before trusting it.

The page shows "Updated <built_at>" and the first selected GW's deadline,
both in the viewer's time zone. Deadlines come from FPL bootstrap `events`.

## Not built yet (suggested 2026-11-11)
Predicted lineups page, captain picks, fixture ticker, DEFCON leaders,
differentials, projections vs results.
