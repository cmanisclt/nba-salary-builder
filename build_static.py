"""Bundle previously downloaded salary records for a static website.

Usage:
  python3 app.py                    # click Refresh HoopsHype salaries in browser
  python3 build_static.py          # creates players-data.js for Netlify

Or: python3 build_static.py --refresh  # retrieve records and bundle in one step
"""
import argparse, json, pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parent
CACHE = ROOT / 'hoopshype_players.json'
OUT = ROOT / 'players-data.js'

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--refresh', action='store_true', help='Download league salary records before bundling')
args = parser.parse_args()

if args.refresh:
    from app import refresh
    payload = refresh()
else:
    if not CACHE.exists():
        parser.error('No salary cache yet. Run python3 app.py and click Refresh HoopsHype salaries, or run with --refresh.')
    payload = json.loads(CACHE.read_text(encoding='utf-8'))

players = payload.get('players', [])
if not isinstance(players, list) or not players:
    parser.error('Salary cache is empty. Refusing to build an empty database.')

# Prevent a partial retrieval from silently posing as a full database.
team_count = payload.get('teams_ok')
if team_count is not None and team_count != 30:
    print(f'WARNING: Only {team_count}/30 NBA teams loaded; check cache errors before publishing.')

usable = [p for p in players if isinstance(p,dict) and p.get('name') and isinstance(p.get('salary'), (int,float)) and p['salary'] > 0]
if not usable:
    parser.error('No valid player salaries found.')
result = {'players': usable, 'season':payload.get('season','2026-27'), 'teams_ok':team_count,
          'exported_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
          'source':'HoopsHype'}
OUT.write_text('window.NBA_SALARY_DATA = '+json.dumps(result,ensure_ascii=False,separators=(',',':'))+';\n', encoding='utf-8')
print(f'Created {OUT.name} with {len(usable)} players. Upload index.html and players-data.js together to Netlify.')
