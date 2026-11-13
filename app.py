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

def refresh():
    allplayers=[];errors=[]
    for team in TEAMS:
        try:
            got=scrape_one(team)
            if not got:raise ValueError('No 2026-27 contracts')
            allplayers+=got
        except Exception as exc:errors.append(f'{team}: {str(exc)[:90]}')
    if not allplayers:raise ValueError('HoopsHype returned no players. '+('; '.join(errors[:3])))
    if len(errors)>7:raise ValueError('Too many teams failed ('+str(len(errors))+'); cached data left unchanged. '+('; '.join(errors[:2])))
    known=positions()
    for p in allplayers:
        p['position']=known.get(norm(p['name']),p['position'])
    unique={norm(p['name']):p for p in allplayers}
    data={'players':list(unique.values()),'teams_ok':30-len(errors),'errors':errors,'season':'2026-27'}
    CACHE.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
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
