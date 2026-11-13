"""NBA Draft Lab server. Run: python app.py ; open http://localhost:8765
Requires only Python standard library. Full salary sync needs internet access.
"""
import json, re, urllib.request, urllib.error, pathlib, threading, unicodedata
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT=pathlib.Path(__file__).parent
CACHE=ROOT/'hoopshype_players.json'
TEAMS='atlanta_hawks boston_celtics brooklyn_nets charlotte_hornets chicago_bulls cleveland_cavaliers dallas_mavericks denver_nuggets detroit_pistons golden_state_warriors houston_rockets indiana_pacers los_angeles_clippers los_angeles_lakers memphis_grizzlies miami_heat milwaukee_bucks minnesota_timberwolves new_orleans_pelicans new_york_knicks oklahoma_city_thunder orlando_magic philadelphia_76ers phoenix_suns portland_trail_blazers sacramento_kings san_antonio_spurs toronto_raptors utah_jazz washington_wizards'.split()
LOCK=threading.Lock()

def grab(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; NBADraftLab/1.0; personal education project)','Accept':'text/html,application/json'})
    with urllib.request.urlopen(req,timeout=18) as r:return r.read().decode('utf-8','replace')

def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',str(s or '').lower()) if c.isalnum())

def get_contracts(payload):
    props=payload.get('props',{}).get('pageProps',{})
    for q in props.get('dehydratedState',{}).get('queries',[]):
        data=q.get('state',{}).get('data',{})
        if isinstance(data,dict):
            contracts=data.get('contracts')
            if isinstance(contracts,dict) and isinstance(contracts.get('contracts'),list):return contracts['contracts']
    return []

def scrape_one(team):
    html=grab(f'https://www.hoopshype.com/salaries/{team}/')
    match=re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',html,re.S)
    if not match:raise ValueError('Could not locate HoopsHype salary data')
    contracts=get_contracts(json.loads(match.group(1)))
    out=[]
    for c in contracts:
        season=next((x for x in c.get('seasons',[]) if str(x.get('season')) in ('2027','2026-27')),None)
        if not season:continue
        val=season.get('salary') or season.get('capAllocation')
        if not val:continue
        person=c.get('player') or {}
        name=c.get('playerName') or ' '.join(filter(None,[person.get('firstName'),person.get('lastName')]))
        if not name:continue
        team_data=person.get('team') or {}
        current_team=' '.join(filter(None,[team_data.get('location'),team_data.get('nickname')])) or team.replace('_',' ').title()
        out.append({'name':name,'salary':int(float(val)),'position':'Unclassified','team':current_team,'source':'HoopsHype 2026-27','twoWay':bool(season.get('twoWayContract'))})
    return out

def positions():
    """Optional position enrichment from ESPN team rosters. HoopsHype salaries do not include position."""
    abbreviations='atl bos bkn cha chi cle dal den det gs hou ind lac lal mem mia mil min no ny okc orl phi phx por sac sa tor utah wsh'.split()
    known={}
    for abbr in abbreviations:
        try:
            url=f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{abbr}/roster'
            obj=json.loads(grab(url))
            for entry in obj.get('athletes',[]):
                for a in (entry.get('items',[]) if 'items' in entry else [entry]):
                    pos=(a.get('position') or {}).get('abbreviation','').upper()
                    labels={'PG':'Guard','SG':'Guard','G':'Guard','SF':'Forward','PF':'Forward','F':'Forward','C':'Center','G-F':'Guard/Forward','F-C':'Forward/Center','C-F':'Forward/Center'}
                    if pos in labels:known[norm(a.get('displayName'))]=labels[pos]
        except Exception:continue
    return known

def scrape_basketball_reference():
    """Fallback: league-wide Basketball-Reference 2026-27 contracts table.

    Depends on pandas and lxml, installed by the GitHub workflow.
    """
    from io import StringIO
    import pandas as pd

    html = grab('https://www.basketball-reference.com/contracts/players.html')
    tables = pd.read_html(StringIO(html))
    for table in tables:
        # pandas may produce either flat or MultiIndex column names.
        cols = [str(c[-1] if isinstance(c, tuple) else c).strip() for c in table.columns]
        name_indices = [i for i, c in enumerate(cols) if c == 'Player']
        salary_indices = [i for i, c in enumerate(cols) if c == '2026-27']
        if not name_indices or not salary_indices:
            continue
        name_col = table.columns[name_indices[0]]
        salary_col = table.columns[salary_indices[0]]
        team_indices = [i for i, c in enumerate(cols) if c in ('Tm', 'Team')]
        team_col = table.columns[team_indices[0]] if team_indices else None
        out = []
        for _, row in table.iterrows():
            name = str(row[name_col]).strip()
            salary_text = str(row[salary_col]).strip()
            if not name or name.lower() in ('nan', 'player'):
                continue
            digits = re.sub(r'[^0-9]', '', salary_text.split('.')[0])
            if not digits:
                continue
            salary = int(digits)
            if salary <= 0:
                continue
            team = str(row[team_col]).strip() if team_col is not None else ''
            out.append({'name':name, 'salary':salary, 'position':'Unclassified',
                        'team':team if team != 'nan' else '',
                        'source':'Basketball-Reference 2026-27', 'twoWay':False})
        if out:
            return out
    raise ValueError('No recognizable 2026-27 contracts table found')


def refresh():
    """Try HoopsHype, then Basketball-Reference; keep old cache on failures."""
    allplayers = []
    errors = []
    source = 'HoopsHype'
    team_count = 0
    for team in TEAMS:
        try:
            got = scrape_one(team)
            if not got:
                raise ValueError('No 2026-27 contracts')
            allplayers.extend(got)
            team_count += 1
        except Exception as exc:
            errors.append(f'{team}: {str(exc)[:120]}')

    # Never publish a partially scraped HoopsHype league as a full dataset.
    if team_count != 30 or len({norm(p['name']) for p in allplayers}) < 300:
        print(f'HoopsHype incomplete ({team_count}/30 teams); trying Basketball-Reference.')
        try:
            allplayers = scrape_basketball_reference()
            source = 'Basketball-Reference'
            team_count = None
            errors = []
        except Exception as exc:
            raise RuntimeError(
                f'Neither data source produced a full league. '
                f'HoopsHype: {team_count}/30 teams; '
                f'Basketball-Reference: {type(exc).__name__}: {exc}. '
                'Existing database preserved.'
            ) from exc

    unique = {norm(p['name']): p for p in allplayers if p.get('name')}
    if len(unique) < 300:
        raise ValueError(f'Only {len(unique)} unique players from {source}; '
                         'refusing partial update. Existing database preserved.')

    known = positions()
    for p in unique.values():
        p['position'] = known.get(norm(p['name']), p.get('position', 'Unclassified'))
    data = {'players':list(unique.values()), 'teams_ok':team_count,
            'errors':errors, 'season':'2026-27', 'source':source}
    # Write only after full validation, atomically.
    temp = CACHE.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(CACHE)
    print(f'{source}: validated {len(unique)} players.')
    return data

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def json_response(self,data,status=200):
        body=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_GET(self):
        if self.path=='/api/players':
            if CACHE.exists():
                try:return self.json_response(json.loads(CACHE.read_text(encoding='utf8')))
                except Exception:pass
            return self.json_response({'players':[]})
        super().do_GET()
    def do_POST(self):
        if self.path!='/api/refresh':return self.json_response({'error':'Not found'},404)
        if not LOCK.acquire(blocking=False):return self.json_response({'error':'Refresh already in progress'},409)
        try:self.json_response(refresh())
        except Exception as exc:self.json_response({'error':str(exc)},502)
        finally:LOCK.release()

if __name__=='__main__':
    print('NBA Draft Lab is running at http://localhost:8765')
    print('Open the URL, then click Refresh HoopsHype salaries to load the full league.')
    ThreadingHTTPServer(('127.0.0.1',8765),Handler).serve_forever()
