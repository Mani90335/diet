#!/usr/bin/env python3
"""FitPlan: dependency-free local Python diet & workout planning server."""
from __future__ import annotations
import csv, io, json, math, os, re, smtplib, sqlite3, threading, time, urllib.error, urllib.parse, urllib.request
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv('FITPLAN_DB', str(ROOT / 'data' / 'fitplan.db')))
STATIC = ROOT / 'static'
TZ = ZoneInfo('Asia/Kolkata')
LOCK = threading.RLock()


def load_env():
    path = ROOT / '.env'
    if not path.exists(): return
    for line in path.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        key,val=line.split('=',1)
        os.environ.setdefault(key.strip(),val.strip().strip('"').strip("'"))

load_env()


def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH,timeout=15)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA busy_timeout=15000')
    return db


def init_db():
    with conn() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS profile (id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS foods (
              id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, name TEXT NOT NULL,
              category TEXT NOT NULL, calories REAL NOT NULL, protein REAL NOT NULL,
              carbs REAL NOT NULL, fat REAL NOT NULL, serving TEXT NOT NULL DEFAULT '1 serving',
              tags TEXT NOT NULL DEFAULT '', UNIQUE(source,name,category));
            CREATE TABLE IF NOT EXISTS plans (day TEXT PRIMARY KEY, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS completed (day TEXT NOT NULL, item TEXT NOT NULL, PRIMARY KEY(day,item));
            CREATE TABLE IF NOT EXISTS weights (day TEXT PRIMARY KEY, weight REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS notifications (day TEXT NOT NULL, channel TEXT NOT NULL,
              sent_at TEXT NOT NULL, PRIMARY KEY(day,channel));
        ''')
        cols={r['name'] for r in db.execute('PRAGMA table_info(foods)')}
        for column in ('fiber_g','calcium_mg','iron_mg','potassium_mg','vitamin_c_mg'):
            if column not in cols:db.execute(f'ALTER TABLE foods ADD COLUMN {column} REAL')
        if 'estimate_note' not in cols:db.execute("ALTER TABLE foods ADD COLUMN estimate_note TEXT NOT NULL DEFAULT ''")
        count=db.execute('SELECT COUNT(*) FROM foods').fetchone()[0]
        if count==0:
            with open(ROOT/'data'/'sample_meals.json',encoding='utf-8') as f: foods=json.load(f)
            add_foods(db,foods,'sample')
        # Bundled, transparent nutrition estimates for the exact public repo item lists.
        with open(ROOT/'data'/'github_diet_estimates.json',encoding='utf-8') as f: curated=json.load(f)
        add_foods(db,curated,'github-estimate:Mani90335/diet')


def add_foods(db, foods, source):
    n=0
    for item in foods:
        try:
            name=str(item['name']).strip()[:120]
            category=normalize_category(item.get('category',''))
            if not name or not category: continue
            vals=[float(item[k]) for k in ('calories','protein','carbs','fat')]
            if not all(math.isfinite(v) and v>=0 for v in vals) or vals[0]>3500:continue
            serving=str(item.get('serving','1 serving'))[:80]
            tags=str(item.get('tags',''))[:250]
            micro=[]
            for k in ('fiber_g','calcium_mg','iron_mg','potassium_mg','vitamin_c_mg'):
                v=item.get(k)
                v=float(v) if v not in ('',None) else None
                if v is not None and (not math.isfinite(v) or v<0):raise ValueError(k)
                micro.append(v)
            note=str(item.get('estimate_note',''))[:300]
            db.execute('''INSERT INTO foods(source,name,category,calories,protein,carbs,fat,serving,tags,
              fiber_g,calcium_mg,iron_mg,potassium_mg,vitamin_c_mg,estimate_note)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source,name,category) DO UPDATE SET
              calories=excluded.calories,protein=excluded.protein,carbs=excluded.carbs,
              fat=excluded.fat,serving=excluded.serving,tags=excluded.tags,
              fiber_g=excluded.fiber_g,calcium_mg=excluded.calcium_mg,
              iron_mg=excluded.iron_mg,potassium_mg=excluded.potassium_mg,
              vitamin_c_mg=excluded.vitamin_c_mg,estimate_note=excluded.estimate_note''',
              (source,name,category,*vals,serving,tags,*micro,note))
            n+=1
        except (KeyError, ValueError,TypeError):pass
    return n


def normalize_category(s):
    s=str(s).lower().strip()
    if s in ('breakfast','morning'):return 'breakfast'
    if s in ('lunch','afternoon'):return 'lunch'
    if s in ('dinner','supper','night'):return 'dinner'
    if s in ('snack','snacks','other','others'):return 'snack'
    return ''


def row_food(row):return dict(row)


def parse_food_text(text, filename, fallback_category=''):
    """Supported: JSON array or {foods:[...]}, CSV or pipe-delimited Markdown table.
    Required nutrition per serving. Never estimate missing recipe nutrition."""
    text=text.lstrip('\ufeff').strip()
    if not fallback_category:
        fallback_category=next((c for c in ('breakfast','lunch','dinner','snack') if c in Path(filename.lower()).name),'')
    ext=Path(filename.lower()).suffix
    records=[]
    if ext=='.json':
        parsed=json.loads(text)
        records=parsed if isinstance(parsed,list) else parsed.get('foods',[])
    else:
        lines=[line.strip() for line in text.splitlines() if line.strip()]
        if ext=='.csv':
            records=list(csv.DictReader(io.StringIO(text)))
        else:
            pipe=[line for line in lines if '|' in line and not re.match(r'^\s*\|?[\s:|-]+\|?\s*$',line)]
            if pipe:
                def split(line):return [v.strip() for v in line.strip().strip('|').split('|')]
                first=split(pipe[0]); keys=[x.lower().replace(' ','_') for x in first]
                header=any(x in keys for x in ('name','meal','item','food'))
                if header:
                    records=[dict(zip(keys,split(line))) for line in pipe[1:]]
                else:
                    records=[dict(zip(('name','calories','protein','carbs','fat','serving'),split(line))) for line in pipe]
    def pick(r,*names):
        for key in names:
            if key in r and r[key] not in (None,''):return r[key]
        return None
    output=[]
    for record in records:
        if not isinstance(record,dict):continue
        r={str(k).strip().lower().replace(' ','_'):v for k,v in record.items()}
        name=pick(r,'name','meal','item','food','dish')
        category=pick(r,'category','meal_type') or fallback_category
        if not name or not normalize_category(category):continue
        try:
            result={'name':str(name),'category':normalize_category(category),
             'calories':float(pick(r,'calories','kcal')),
             'protein':float(pick(r,'protein','protein_g')),
             'carbs':float(pick(r,'carbs','carbs_g','carbohydrates')),
             'fat':float(pick(r,'fat','fat_g')),
             'serving':str(pick(r,'serving','portion','quantity') or '1 serving'),
             'tags':str(pick(r,'tags','diet_type') or ''),
             **{k:(float(r[k]) if r.get(k) not in ('',None) else None)
                for k in ('fiber_g','calcium_mg','iron_mg','potassium_mg','vitamin_c_mg')},
             'estimate_note':str(r.get('estimate_note') or '')}
            output.append(result)
        except (ValueError,TypeError):pass
    return output


def parse_numbered_items(text):
    """Read GitHub's extensionless numbered plain-text recipe inventories."""
    items=[]
    for line in text.splitlines():
        match=re.match(r'^\s*(?:\d+[.)]\s+|[-*]\s+)(.+?)\s*$',line)
        if match:
            name=match.group(1).strip().strip('`')
            if name and len(name)>1:items.append(name)
    return list(dict.fromkeys(items))


def github_import(url):
    parsed=urllib.parse.urlparse(url)
    if parsed.hostname not in ('github.com','www.github.com'):
        raise ValueError('Enter a public github.com repository URL.')
    parts=[x for x in parsed.path.split('/') if x]
    if len(parts)<2:raise ValueError('Repository URL should be github.com/owner/repo')
    owner,repo=parts[:2];repo=repo.removesuffix('.git')
    def get(url):
        req=urllib.request.Request(url,headers={'User-Agent':'FitPlanLocal/2.0','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(req,timeout=12) as resp:return resp.read()
    api=f'https://api.github.com/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}'
    meta=json.loads(get(api));branch=meta['default_branch']
    tree=json.loads(get(api+'/git/trees/'+urllib.parse.quote(branch,safe='')+'?recursive=1'))
    eligible=[]
    for item in tree.get('tree',[]):
        if item.get('type')!='blob':continue
        path=item['path']; name=Path(path.lower()).name
        if Path(name).suffix not in ('','.csv','.json','.md','.txt'):continue
        if any(key in name for key in ('breakfast','curries','lunch','dinner','other food','snack')):
            eligible.append(path)
    if not eligible:raise ValueError('No compatible breakfast, curries, or other-food files found.')
    curated=json.loads((ROOT/'data'/'github_diet_estimates.json').read_text())
    curated_by_name={f['name'].casefold().replace(' ','').replace('+',''):f for f in curated}
    foods=[];report=[]
    for path in eligible[:25]:
        raw='https://raw.githubusercontent.com/'+urllib.parse.quote(owner)+'/'+urllib.parse.quote(repo)+'/'+urllib.parse.quote(branch,safe='')+'/'+urllib.parse.quote(path,safe='/')
        try:
            content=get(raw).decode('utf-8')
            category='breakfast' if 'breakfast' in path.lower() else 'lunch' if 'curr' in path.lower() else 'snack'
            parsed_foods=parse_food_text(content,path,category)
            unknown=[]
            if not parsed_foods:
                for name in parse_numbered_items(content):
                    item=curated_by_name.get(name.casefold().replace(' ','').replace('+',''))
                    if item:
                        entries=[x.copy() for x in curated if x['name']==item['name'] and x['source_file'].lower()==Path(path).name.lower()]
                        parsed_foods.extend(entries)
                    else:unknown.append(name)
            foods.extend(parsed_foods)
            report.append({'file':path,'imported':len(parsed_foods),'unmatched':unknown})
        except (UnicodeDecodeError,urllib.error.URLError,ValueError) as exc:
            report.append({'file':path,'imported':0,'error':str(exc)[:140]})
    return foods,report


def get_profile(db):
    row=db.execute('SELECT data FROM profile WHERE id=1').fetchone()
    return json.loads(row['data']) if row else None


def calculations(p):
    weight=float(p['weight']);height=float(p['height']);age=int(p['age']);target=float(p['target']);days=int(p['days'])
    sex=p['sex']; factor={'sedentary':1.2,'light':1.375,'moderate':1.55,'active':1.725}[p['activity']]
    bmr=10*weight+6.25*height-5*age+(5 if sex=='male' else -161)
    tdee=bmr*factor
    required=(weight-target)*7700/days
    adjusted=max(-450,min(500,required))
    calories=round(tdee-adjusted)
    floor=1500 if sex=='male' else 1200
    warnings=[]
    if required>500:warnings.append('Requested deadline would require a large estimated deficit; the planner limits the deficit and may take longer.')
    if required < -450:warnings.append('Requested weight gain pace is aggressive; daily surplus is limited in this starter planner.')
    if calories<floor:
        calories=floor
        warnings.append('Calorie target raised to a basic screening floor. Individual requirements may differ; consult a qualified clinician/dietitian.')
    if abs((weight-target)*7/days)>0.9:warnings.append('The requested weekly weight change is rapid; review whether your timeframe is realistic.')
    if target<1 or weight<1:raise ValueError('Weights must be positive.')
    protein=round(1.2*weight)
    fat=round(calories*.27/9)
    carbs=max(0,round((calories-4*protein-9*fat)/4))
    bmi=weight/(height/100)**2
    if bmi<18.5:warnings.append('BMI is below the standard adult screening range; seek individualized advice before aiming to lose weight.')
    if target/(height/100)**2<18.5:warnings.append('Your target weight corresponds to a BMI under 18.5; review the target with a qualified professional.')
    return {'bmi':round(bmi,1),'target_bmi':round(target/(height/100)**2,1),
      'bmr':round(bmr),'tdee':round(tdee),'calories':calories,'protein':protein,
      'fat':fat,'carbs':carbs,'weekly_change':round((weight-target)*7/days,2),
      'warnings':warnings,'requested_calories':round(tdee-required)}


def validate_profile(p):
    for field in ('age','height','weight','target','days','sex','activity'):
        if field not in p:raise ValueError('Missing '+field)
    for field,lo,hi in (('age',18,100),('height',100,230),('weight',30,350),('target',30,350),('days',7,1825)):
        try:v=float(p[field])
        except (ValueError,TypeError):raise ValueError('Invalid '+field)
        if not math.isfinite(v) or not lo<=v<=hi:raise ValueError(f'{field} must be between {lo} and {hi}')
    if p['sex'] not in ('male','female') or p['activity'] not in ('sedentary','light','moderate','active'):
        raise ValueError('Invalid profile selection')
    if len(str(p.get('email','')))>200:raise ValueError('Email too long')
    return calculations(p)

WORKOUTS=[('Upper body strength','Push-ups / chest press, rows, shoulder press, curls. Adjust sets and load to experience.', 'strength'),
 ('Lower body strength','Squats or sit-to-stands, hip hinges, lunges, calf raises. Start light.', 'strength'),
 ('Easy cardio','20–40 minutes of comfortable walking or cycling; scale to ability.','cardio'),
 ('Full body strength','Squat, hinge, push, pull, and core movements; use appropriate loads.','strength'),
 ('Active recovery','Gentle walk and flexibility or mobility practice.','recovery'),
 ('Cardio + mobility','Moderate cycling or walking plus stretching; choose a suitable duration.','cardio'),
 ('Rest day','Rest, sleep, and recovery. Optional light walk.','rest')]

def make_day_plan(db, day, profile, metrics):
    foods=[dict(r) for r in db.execute('SELECT * FROM foods ORDER BY name').fetchall()]
    avoid=[x.strip().lower() for x in str(profile.get('avoid','')).split(',') if x.strip()]
    diet=profile.get('diet','all')
    def allowed(r):
        phrase=(r['name']+' '+r['tags']).lower()
        if any(word in phrase for word in avoid):return False
        if diet=='vegetarian' and ('nonveg' in phrase or 'chicken' in phrase or 'fish' in phrase or 'meat' in phrase or 'egg' in phrase):return False
        if diet=='vegan' and any(w in phrase for w in ('nonveg','chicken','fish','meat','egg','milk','paneer','curd','yogurt','ghee','cheese')):return False
        return True
    foods=[f for f in foods if allowed(f)]
    allocations={'breakfast':.24,'lunch':.34,'snack':.12,'dinner':.30}
    daynum=date.fromisoformat(day).toordinal()
    result=[]
    def scale(f,m):
        return {'id':'meal_'+category,'category':category,'name':f['name'],
            'serving':f'{m:g} × {f["serving"]}',
            **{k:round((f[k] or 0)*m,1) for k in ('calories','protein','carbs','fat','fiber_g','calcium_mg','iron_mg','potassium_mg','vitamin_c_mg')},
            'estimate_note':f.get('estimate_note') or 'Nutrition depends on recipe and portion size.'}
    for category,share in allocations.items():
        pool=[f for f in foods if f['category']==category and f['calories']>0]
        if not pool:continue
        desired=metrics['calories']*share
        # For lunch/dinner, curries are sides: pair with rice/roti instead of calling them a full meal.
        candidates=[]
        for f in pool:
            if category in ('lunch','dinner') and f['source']=='github-estimate:Mani90335/diet' and f['name'] in ('Tomato','Bottle guard','Beerakaya','Egg fry','Egg onion soup','Chicken','Egg tomato','Millmaker','Dall- 3 types','Aloo'):
                for base_name,base_cal,base_pro,base_carbs,base_fat,base_fiber in [('150 g cooked rice',195,4,43,0.4,0.5),('2 medium chapatis',220,7,40,4,6)]:
                    f2=dict(f);f2['name']=f['name']+' + '+base_name;f2['serving']=f['serving']+' + '+base_name
                    for key,add in [('calories',base_cal),('protein',base_pro),('carbs',base_carbs),('fat',base_fat),('fiber_g',base_fiber)]:f2[key]=(f2.get(key) or 0)+add
                    candidates.append(f2)
            else:candidates.append(f)
        scored=[]
        for f in candidates:
            for multiplier in (.75,1,1.25,1.5,2):
                score=abs(f['calories']*multiplier-desired)/max(desired,1)
                # Avoid over-selecting very low-protein meals when similar energy alternatives exist.
                score+=max(0,(metrics['protein']*share-f['protein']*multiplier))/max(1,metrics['protein'])*.2
                scored.append((score,f,multiplier))
        scored.sort(key=lambda x:x[0]);shortlist=scored[:min(6,len(scored))]
        if shortlist:
            _,f,m=shortlist[daynum%len(shortlist)]
            result.append(scale(f,m))
    wname,wdesc,wtype=WORKOUTS[date.fromisoformat(day).weekday()]
    totals={key:round(sum(item[key] for item in result),1) for key in ('calories','protein','carbs','fat','fiber_g','calcium_mg','iron_mg','potassium_mg','vitamin_c_mg')}
    warnings=[]
    if len(result)<4:warnings.append('Missing meal categories or suitable foods. Add complete recipes to your library.')
    if abs(totals['calories']-metrics['calories'])>metrics['calories']*.15:warnings.append('Selected recipes differ substantially from your calorie target; expand the library or adjust serving options.')
    if totals['protein']<metrics['protein']*.75:warnings.append('Selected recipes fall short of the example protein goal. Review nutrition and recipe options.')
    if any(not m.get('fiber_g') for m in result):warnings.append('Some recipe micronutrient fields are unknown or zero; daily micronutrient totals may be incomplete.')
    warnings.append('All bundled GitHub food nutrition values are generic serving estimates; verify your cooked recipe, oil and portion sizes.')
    return {'day':day,'meals':result,'workout':{'name':wname,'description':wdesc,'type':wtype},
      'totals':totals,'warnings':warnings}


def ensure_plan(db,day,regenerate=False):
    if not regenerate:
        row=db.execute('SELECT data FROM plans WHERE day=?',(day,)).fetchone()
        if row:return json.loads(row['data'])
    p=get_profile(db)
    if not p:return None
    metrics=calculations(p);plan=make_day_plan(db,day,p,metrics)
    db.execute('INSERT OR REPLACE INTO plans(day,data) VALUES(?,?)',(day,json.dumps(plan),))
    return plan


def today():return datetime.now(TZ).date().isoformat()


def notification_text(p,metrics,plan):
    lines=[f'Your FitPlan for {plan["day"]}',f'Calorie target: {metrics["calories"]} kcal',
       f'Planned meals: {plan["totals"]["calories"]} kcal',
       f'Estimated fiber: {plan["totals"].get("fiber_g", "unknown")} g', '']
    for m in plan['meals']:
        lines.append(f'{m["category"].title()}: {m["name"]} ({m["serving"]}) — {m["calories"]} kcal')
    lines+=['',f'Workout: {plan["workout"]["name"]}',plan['workout']['description'],'',
            'Plans are estimates. Adjust to your needs and seek professional advice for medical concerns.']
    return '\n'.join(lines)


def send_email(subject,body,to):
    host=os.getenv('SMTP_HOST',''); user=os.getenv('SMTP_USER','');pw=os.getenv('SMTP_PASSWORD','')
    if not host or not to:raise ValueError('Configure SMTP_HOST and an email address first.')
    port=int(os.getenv('SMTP_PORT','587'))
    msg=EmailMessage();msg['Subject']=subject;msg['From']=os.getenv('SMTP_FROM',user);msg['To']=to;msg.set_content(body)
    if port==465:
        with smtplib.SMTP_SSL(host,port,timeout=15) as smtp:
            if user:smtp.login(user,pw)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host,port,timeout=15) as smtp:
            smtp.starttls()
            if user:smtp.login(user,pw)
            smtp.send_message(msg)


def send_whatsapp(body, recipient):
    token=os.getenv('WHATSAPP_TOKEN','');phone_id=os.getenv('WHATSAPP_PHONE_NUMBER_ID','');template=os.getenv('WHATSAPP_TEMPLATE','')
    if not token or not phone_id or not template:raise ValueError('WhatsApp requires WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID and an approved WHATSAPP_TEMPLATE.')
    # Proactive WhatsApp business messages use pre-approved templates.
    payload={'messaging_product':'whatsapp','to':recipient,'type':'template',
      'template':{'name':template,'language':{'code':os.getenv('WHATSAPP_TEMPLATE_LANG','en_US')}}}
    endpoint='https://graph.facebook.com/'+os.getenv('WHATSAPP_API_VERSION','v23.0')+'/'+phone_id+'/messages'
    req=urllib.request.Request(endpoint,data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=15) as resp:return resp.read().decode()


def notify(db,day,channel, force=False):
    p=get_profile(db)
    if not p:raise ValueError('Save your profile first.')
    plan=ensure_plan(db,day)
    if not plan:raise ValueError('No plan available.')
    existing=db.execute('SELECT 1 FROM notifications WHERE day=? AND channel=?',(day,channel)).fetchone()
    if existing and not force:return 'Already sent today'
    body=notification_text(p,calculations(p),plan)
    if channel=='email':send_email('Your FitPlan — '+day,body,p.get('email',''))
    elif channel=='whatsapp':
        if not p.get('phone'):raise ValueError('Enter your WhatsApp number in your profile.')
        send_whatsapp(body,p['phone'])
    else:raise ValueError('Unsupported channel')
    db.execute('INSERT OR REPLACE INTO notifications(day,channel,sent_at) VALUES(?,?,?)',
               (day,channel,datetime.now(TZ).isoformat()))
    return 'Sent successfully'


def scheduler_loop():
    while True:
        try:
            now=datetime.now(TZ)
            with LOCK,conn() as db:
                p=get_profile(db)
                if p and p.get('notifications_enabled') and now.strftime('%H:%M')>=p.get('notify_time','07:00'):
                    channel=p.get('channel','email')
                    if not db.execute('SELECT 1 FROM notifications WHERE day=? AND channel=?',(now.date().isoformat(),channel)).fetchone():
                        try:notify(db,now.date().isoformat(),channel)
                        except Exception as exc:print('Notification delivery failed:',str(exc),flush=True)
        except Exception as exc:print('Scheduler warning:',str(exc),flush=True)
        time.sleep(60)

class App(BaseHTTPRequestHandler):
    def log_message(self,format,*args):print('%s %s'%(self.log_date_time_string(),format%args),flush=True)
    def respond(self,data,status=200):
        payload=json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(payload)));self.send_header('Cache-Control','no-store')
        self.end_headers();self.wfile.write(payload)
    def body(self):
        length=int(self.headers.get('Content-Length','0'))
        if length>2_000_000:raise ValueError('Request exceeds 2 MB')
        return json.loads(self.rfile.read(length).decode() or '{}')
    def do_GET(self):
        url=urllib.parse.urlparse(self.path); path=url.path
        if path=='/' or path.startswith('/static/'):
            f=(STATIC/'index.html') if path=='/' else STATIC/path[len('/static/'):]
            try:
                if not f.resolve().is_relative_to(STATIC.resolve()) or not f.is_file():raise FileNotFoundError()
                payload=f.read_bytes();mime={'.html':'text/html','.css':'text/css','.js':'application/javascript','.svg':'image/svg+xml'}.get(f.suffix,'application/octet-stream')
                self.send_response(200);self.send_header('Content-Type',mime+'; charset=utf-8');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
            except FileNotFoundError:self.send_error(404)
            return
        try:
            with LOCK,conn() as db:
                if path=='/api/state':
                    p=get_profile(db); metrics=calculations(p) if p else None;current=today()
                    plan=ensure_plan(db,current) if p else None
                    done=[dict(r) for r in db.execute('SELECT day,item FROM completed WHERE day>=?',((date.today()-timedelta(days=14)).isoformat(),))]
                    weights=[dict(r) for r in db.execute('SELECT day,weight FROM weights ORDER BY day DESC LIMIT 60')][::-1]
                    if p:
                        height_m=float(p['height'])/100
                        for entry in weights:
                            entry['bmi']=round(entry['weight']/(height_m**2),1)
                    self.respond({'profile':p,'metrics':metrics,'today':current,'plan':plan,
                      'completed':done,'weights':weights,'food_count':db.execute('SELECT COUNT(*) FROM foods').fetchone()[0],
                      'source_counts':[dict(r) for r in db.execute('SELECT source,COUNT(*) AS count FROM foods GROUP BY source')],
                      'notifications':[dict(r) for r in db.execute('SELECT * FROM notifications ORDER BY sent_at DESC LIMIT 10')]})
                elif path=='/api/foods':
                    self.respond({'foods':[dict(r) for r in db.execute('SELECT * FROM foods ORDER BY category,name')]})
                elif path=='/api/week':
                    start=date.fromisoformat(urllib.parse.parse_qs(url.query).get('start',[today()])[0])
                    result=[ensure_plan(db,(start+timedelta(days=i)).isoformat()) for i in range(7)]
                    self.respond({'plans':result})
                elif path=='/api/notification-preview':
                    p=get_profile(db)
                    self.respond({'text':notification_text(p,calculations(p),ensure_plan(db,today())) if p else 'Save your profile first.'})
                else:self.respond({'error':'Not found'},404)
        except (ValueError,KeyError,TypeError) as exc:self.respond({'error':str(exc)},400)
        except Exception as exc:print('GET error',repr(exc));self.respond({'error':'Unexpected server error'},500)
    def do_POST(self):
        try:
            data=self.body();path=urllib.parse.urlparse(self.path).path
            with LOCK,conn() as db:
                if path=='/api/profile':
                    metrics=validate_profile(data)
                    db.execute('INSERT OR REPLACE INTO profile(id,data) VALUES(1,?)',(json.dumps(data),))
                    db.execute('DELETE FROM plans WHERE day>=?',(today(),))
                    self.respond({'ok':True,'metrics':metrics})
                elif path=='/api/import-text':
                    filename=str(data.get('filename','meals.csv'))[:200]
                    foods=parse_food_text(str(data.get('text','')),filename,data.get('category',''))
                    if not foods:raise ValueError('No valid meals found. Every row needs name, calories, protein, carbs, fat and meal category.')
                    source='upload:'+filename
                    db.execute('DELETE FROM foods WHERE source=?',(source,))
                    count=add_foods(db,foods,source)
                    db.execute('DELETE FROM plans WHERE day>=?',(today(),))
                    self.respond({'ok':True,'count':count})
                elif path=='/api/import-github':
                    foods,report=github_import(str(data.get('url','')))
                    if not foods:self.respond({'error':'No meals with complete nutritional fields found.','files':report},400);return
                    source=('github-estimate:Mani90335/diet' if 'github.com/Mani90335/diet' in str(data['url']) else 'github:'+str(data['url']).strip())
                    db.execute('DELETE FROM foods WHERE source=?',(source,))
                    count=add_foods(db,foods,source)
                    db.execute('DELETE FROM plans WHERE day>=?',(today(),))
                    self.respond({'ok':True,'count':count,'files':report})
                elif path=='/api/clear-samples':
                    db.execute("DELETE FROM foods WHERE source='sample'")
                    db.execute('DELETE FROM plans WHERE day>=?',(today(),))
                    self.respond({'ok':True})
                elif path=='/api/add-food':
                    if not normalize_category(data.get('category','')):raise ValueError('Choose a valid meal category')
                    if not all(k in data for k in ('name','calories','protein','carbs','fat')):raise ValueError('All nutrition fields are required')
                    if add_foods(db,[data],'manual')!=1:raise ValueError('Invalid meal or nutrition values')
                    db.execute('DELETE FROM plans WHERE day>=?',(today(),))
                    self.respond({'ok':True})
                elif path=='/api/complete':
                    day=date.fromisoformat(data.get('day',today())).isoformat();item=str(data.get('item',''))
                    if item not in ('meal_breakfast','meal_lunch','meal_dinner','meal_snack','workout'):raise ValueError('Unknown checklist item')
                    if data.get('done'):db.execute('INSERT OR IGNORE INTO completed(day,item) VALUES(?,?)',(day,item))
                    else:db.execute('DELETE FROM completed WHERE day=? AND item=?',(day,item))
                    self.respond({'ok':True})
                elif path=='/api/weight':
                    day=date.fromisoformat(data.get('day',today())).isoformat();value=float(data['weight'])
                    if not math.isfinite(value) or not 20<=value<=400:raise ValueError('Enter a valid weight in kg')
                    db.execute('INSERT OR REPLACE INTO weights(day,weight) VALUES(?,?)',(day,value))
                    self.respond({'ok':True})
                elif path=='/api/regenerate':
                    start=date.fromisoformat(data.get('start',today()))
                    for i in range(7):ensure_plan(db,(start+timedelta(days=i)).isoformat(),True)
                    self.respond({'ok':True})
                elif path=='/api/send':
                    ch=data.get('channel','email')
                    result=notify(db,today(),ch,True)
                    self.respond({'ok':True,'message':result})
                else:self.respond({'error':'Not found'},404)
        except (ValueError,KeyError,TypeError,json.JSONDecodeError,urllib.error.URLError,urllib.error.HTTPError) as exc:
            self.respond({'error':str(exc)},400)
        except Exception as exc:print('POST error',repr(exc));self.respond({'error':'Unexpected server error'},500)

if __name__=='__main__':
    init_db()
    threading.Thread(target=scheduler_loop,name='daily-notifications',daemon=True).start()
    host=os.getenv('FITPLAN_HOST','127.0.0.1');port=int(os.getenv('FITPLAN_PORT','8000'))
    print(f'\nFitPlan is running at http://{host}:{port}\nKeep this terminal open for reminders. Press Ctrl+C to stop.\n',flush=True)
    try:ThreadingHTTPServer((host,port),App).serve_forever()
    except KeyboardInterrupt:print('\nStopped.')
