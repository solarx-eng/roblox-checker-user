import os
import json
import threading
import urllib.parse
import webbrowser
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
from roblox_username_checker import RobloxUsernameChecker
import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'rbxscan_secret_key_2024')
checker = RobloxUsernameChecker(rate_limit_delay=0.2)

DB_FILE = 'usernames.db'
WEBHOOKS_FILE = 'webhooks.json'
WEBHOOK_KEYS = ['4L', '4C', '5L', '5C', '5N', '6L', '6C', '6N']

AUTH_USERNAME = os.environ.get('AUTH_USERNAME', 'admin')
AUTH_PASSWORD = os.environ.get('AUTH_PASSWORD', 'admin')

DISCORD_CLIENT_ID = os.environ.get('DISCORD_CLIENT_ID', '')
DISCORD_CLIENT_SECRET = os.environ.get('DISCORD_CLIENT_SECRET', '')
DISCORD_REDIRECT_URI = os.environ.get('DISCORD_REDIRECT_URI', 'https://roblox-checker-user-j6lh.onrender.com/discord/callback')
DISCORD_SCOPE = 'identify'
DISCORD_AUTHORIZE_URL = 'https://discord.com/api/oauth2/authorize'
DISCORD_TOKEN_URL = 'https://discord.com/api/oauth2/token'
DISCORD_API_ME = 'https://discord.com/api/users/@me'


# ─── Database ────────────────────────────────────────────────────────────────

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS available_names
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, type TEXT,
                  found_at TIMESTAMP, found_by TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS discord_whitelist
                 (id INTEGER PRIMARY KEY, discord_id TEXT UNIQUE,
                  nickname TEXT, added_at TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('open_access', '1')")
    conn.commit()
    conn.close()


def get_setting(key):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key = ?', (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def set_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
    conn.commit()
    conn.close()


def get_whitelist():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT discord_id, nickname, added_at FROM discord_whitelist ORDER BY added_at DESC')
    rows = c.fetchall()
    conn.close()
    return rows


def add_to_whitelist(discord_id, nickname):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO discord_whitelist (discord_id, nickname, added_at) VALUES (?, ?, ?)',
                  (discord_id.strip(), nickname.strip(), datetime.now()))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def remove_from_whitelist(discord_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM discord_whitelist WHERE discord_id = ?', (discord_id,))
    conn.commit()
    conn.close()


def is_whitelisted(discord_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT 1 FROM discord_whitelist WHERE discord_id = ?', (discord_id,))
    row = c.fetchone()
    conn.close()
    return row is not None


def add_to_db(username, username_type, found_by='scanner'):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO available_names (username, type, found_at, found_by) VALUES (?, ?, ?, ?)',
                  (username, username_type, datetime.now(), found_by))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_all_names():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT username, type, found_at FROM available_names ORDER BY found_at DESC')
    rows = c.fetchall()
    conn.close()
    return rows


def get_names_by_type(username_type):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT username, type, found_at FROM available_names WHERE type = ? ORDER BY found_at DESC',
              (username_type,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_stats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM available_names')
    total = c.fetchone()[0]
    c.execute('SELECT type, COUNT(*) FROM available_names GROUP BY type')
    by_type = dict(c.fetchall())
    c.execute("SELECT COUNT(*) FROM available_names WHERE DATE(found_at) = DATE('now','localtime')")
    today = c.fetchone()[0]
    conn.close()
    return {'total': total, 'by_type': by_type, 'today': today}


def load_webhooks():
    if os.path.exists(WEBHOOKS_FILE):
        try:
            with open(WEBHOOKS_FILE, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
                return {k: data.get(k, '') for k in WEBHOOK_KEYS}
        except Exception:
            pass
    return {k: '' for k in WEBHOOK_KEYS}


def save_webhooks(webhooks):
    with open(WEBHOOKS_FILE, 'w', encoding='utf-8') as fh:
        json.dump({k: webhooks.get(k, '') for k in WEBHOOK_KEYS}, fh, indent=2)


def get_webhook_url(username_type):
    env = os.environ.get(f'WEBHOOK_{username_type.upper()}')
    if env:
        return env
    return load_webhooks().get(username_type.upper(), '')


def send_webhook(username, username_type):
    url = get_webhook_url(username_type)
    if not url:
        return
    try:
        requests.post(url, json={
            'username': username,
            'type': username_type,
            'timestamp': datetime.now().isoformat()
        }, timeout=5)
    except Exception:
        pass


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def is_authenticated():
    return session.get('logged_in') is True


@app.before_request
def require_login():
    public = ('login', 'static', 'discord_login', 'discord_callback')
    if request.endpoint in public:
        return
    if not is_authenticated():
        return redirect(url_for('login'))


# ─── HTML Templates ───────────────────────────────────────────────────────────

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>RBXScan</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Syne:wght@400;600;700&display=swap" rel="stylesheet"/>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{min-height:100vh;background:#060a12;display:grid;place-items:center;font-family:'Syne',sans-serif;color:#e8eaf6}
.card{width:min(400px,90vw);background:#0d1421;border:1px solid rgba(255,255,255,0.08);border-radius:20px;padding:36px}
.logo{font-size:22px;font-weight:700;margin-bottom:28px;text-align:center}
.logo span{color:#6c63ff}
.err{background:rgba(255,101,132,0.1);border:1px solid rgba(255,101,132,0.3);color:#ff6584;padding:10px 14px;border-radius:10px;font-size:13px;margin-bottom:18px;font-family:'JetBrains Mono',monospace}
label{font-size:11px;color:#6b7280;font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:6px}
input{width:100%;padding:12px 14px;border-radius:10px;border:1px solid rgba(255,255,255,0.08);background:#080c14;color:#e8eaf6;font-family:'JetBrains Mono',monospace;font-size:13px;outline:none;margin-bottom:14px}
input:focus{border-color:#6c63ff}
.btn{width:100%;padding:13px;border-radius:10px;border:none;font-family:'Syne',sans-serif;font-size:14px;font-weight:700;cursor:pointer;transition:all .2s}
.btn-primary{background:#6c63ff;color:#fff;margin-bottom:12px}
.btn-primary:hover{filter:brightness(1.15)}
.btn-discord{background:#5865f2;color:#fff}
.btn-discord:hover{filter:brightness(1.1)}
.divider{text-align:center;color:#6b7280;font-size:12px;margin:14px 0;font-family:'JetBrains Mono',monospace}
</style>
</head>
<body>
<div class="card">
  <div class="logo">RBX<span>Scan</span></div>
  {% if error %}<div class="err">{{ error }}</div>{% endif %}
  <form method="post">
    <label>Username</label>
    <input name="username" type="text" placeholder="admin" autocomplete="username" required/>
    <label>Password</label>
    <input name="password" type="password" placeholder="••••••••" autocomplete="current-password" required/>
    <button class="btn btn-primary" type="submit">Sign In</button>
  </form>
  {% if discord_enabled %}
  <div class="divider">or</div>
  <button class="btn btn-discord" onclick="window.location='/discord_login'">Login with Discord</button>
  {% endif %}
</div>
</body>
</html>"""


USER_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>RBXScan</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Syne:wght@400;600;700&display=swap" rel="stylesheet"/>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#060a12;--panel:#0d1421;--border:rgba(255,255,255,0.07);
  --accent:#6c63ff;--green:#00e5a0;--amber:#ffb347;--red:#ff6584;
  --text:#e8eaf6;--muted:#6b7280;
  --mono:'JetBrains Mono',monospace;--sans:'Syne',sans-serif
}
body{background:var(--bg);color:var(--text);font-family:var(--sans);min-height:100vh}
.app{max-width:1000px;margin:0 auto;padding:24px 16px}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:32px;padding-bottom:16px;border-bottom:1px solid var(--border)}
.logo{font-size:20px;font-weight:700}.logo span{color:var(--accent)}
.topbar-right{display:flex;align-items:center;gap:20px}
.nav-link{color:var(--muted);text-decoration:none;font-size:12px;font-family:var(--mono);transition:color .2s}.nav-link:hover{color:var(--text)}
.status-wrap{display:flex;align-items:center;gap:6px}
.dot{width:7px;height:7px;border-radius:50%;background:var(--muted);transition:background .3s}
.dot.on{background:var(--green);box-shadow:0 0 6px var(--green)}
.stxt{font-size:11px;color:var(--muted);font-family:var(--mono)}
.section-lbl{font-size:10px;color:var(--muted);font-family:var(--mono);text-transform:uppercase;letter-spacing:1.5px;margin-bottom:12px}
.mode-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:24px}
.mode-btn{padding:14px 8px;border-radius:12px;background:var(--panel);border:1px solid var(--border);color:var(--muted);cursor:pointer;font-family:var(--mono);font-size:11px;text-align:center;transition:all .18s;line-height:1.5}
.mode-btn .mc{font-size:17px;font-weight:700;display:block;color:var(--text);margin-bottom:3px}
.mode-btn:hover{border-color:rgba(108,99,255,0.5);color:var(--text)}
.mode-btn.active{border-color:var(--accent);background:rgba(108,99,255,0.1)}
.mode-btn.active .mc{color:var(--accent)}
.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:16px}
.stat{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px}
.sl{font-size:10px;color:var(--muted);font-family:var(--mono);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
.sv{font-size:24px;font-weight:700;font-family:var(--mono);line-height:1}
.sv.ca{color:var(--accent)}.sv.cg{color:var(--green)}.sv.cb{color:var(--amber)}
.batch-row{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:14px 18px;margin-bottom:16px;display:flex;align-items:center;gap:20px;flex-wrap:wrap}
.bi{display:flex;align-items:center;gap:8px;font-family:var(--mono);font-size:12px;color:var(--muted)}
.pill{padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;font-family:var(--mono)}
.pa{background:rgba(108,99,255,0.15);color:var(--accent);border:1px solid rgba(108,99,255,0.25)}
.pb{background:rgba(255,179,71,0.12);color:var(--amber);border:1px solid rgba(255,179,71,0.2)}
.prog-wrap{flex:1;min-width:100px;height:3px;background:rgba(255,255,255,0.06);border-radius:2px;overflow:hidden}
.prog-bar{height:100%;background:var(--accent);width:0%;transition:width .25s;border-radius:2px}
.last-found{background:rgba(0,229,160,0.04);border:1px solid rgba(0,229,160,0.15);border-radius:12px;padding:14px 18px;margin-bottom:16px;display:none;align-items:center;justify-content:space-between}
.last-found.show{display:flex}
.lf-lbl{font-size:10px;color:var(--green);font-family:var(--mono);text-transform:uppercase;letter-spacing:1px;margin-bottom:3px}
.lf-name{font-size:20px;font-weight:700;font-family:var(--mono);color:var(--green)}
.lf-time{font-size:11px;color:var(--muted);font-family:var(--mono)}
.ctrl-row{display:grid;grid-template-columns:1fr 1fr auto auto;gap:10px;margin-bottom:20px;align-items:end}
.cg label{font-size:10px;color:var(--muted);font-family:var(--mono);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:6px}
.cg input{width:100%;padding:11px 13px;border-radius:9px;border:1px solid var(--border);background:var(--panel);color:var(--text);font-family:var(--mono);font-size:13px;outline:none}
.cg input:focus{border-color:var(--accent)}
.btn{padding:11px 22px;border-radius:9px;border:none;font-family:var(--sans);font-size:13px;font-weight:700;cursor:pointer;transition:all .2s;white-space:nowrap}
.btn-go{background:var(--accent);color:#fff}.btn-go:hover{filter:brightness(1.12)}.btn-go:disabled{opacity:.4;cursor:not-allowed}
.btn-stop{background:rgba(255,101,132,0.12);color:var(--red);border:1px solid rgba(255,101,132,0.25)}.btn-stop:disabled{opacity:.3;cursor:not-allowed}
.feed-wrap{background:var(--panel);border:1px solid var(--border);border-radius:12px;overflow:hidden}
.feed-hdr{padding:13px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
.feed-title{font-size:13px;font-weight:700}
.feed-meta{font-size:11px;color:var(--muted);font-family:var(--mono)}
.feed-body{height:340px;overflow-y:auto;padding:6px 0}
.feed-body::-webkit-scrollbar{width:3px}.feed-body::-webkit-scrollbar-thumb{background:var(--border);border-radius:2px}
.fi{display:flex;align-items:center;justify-content:space-between;padding:9px 18px;font-family:var(--mono);font-size:12px;transition:background .12s;border-left:2px solid transparent}
.fi:hover{background:rgba(255,255,255,0.02)}
.fi.hit{border-left-color:var(--green)}
.fi .fu{color:var(--text);font-weight:500}.fi.hit .fu{color:var(--green)}
.fi .fm{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:11px}
.tag{padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700}
.tag-av{background:rgba(0,229,160,0.1);color:var(--green)}
.tag-tk{background:rgba(255,255,255,0.04);color:var(--muted)}
.empty{display:flex;align-items:center;justify-content:center;height:100%;color:var(--muted);font-family:var(--mono);font-size:12px}
@media(max-width:600px){.mode-grid{grid-template-columns:repeat(2,1fr)}.stats-grid{grid-template-columns:repeat(2,1fr)}.ctrl-row{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<div class="app">
  <div class="topbar">
    <div class="logo">RBX<span>Scan</span></div>
    <div class="topbar-right">
      <a href="/admin" class="nav-link">Admin</a>
      <a href="/logout" class="nav-link">Logout</a>
      <div class="status-wrap">
        <span class="dot" id="dot"></span>
        <span class="stxt" id="stxt">idle</span>
      </div>
    </div>
  </div>

  <div class="section-lbl">Select Mode</div>
  <div class="mode-grid">
    <button class="mode-btn active" onclick="setMode('4L')" data-m="4L"><span class="mc">4L</span>4 Letter</button>
    <button class="mode-btn" onclick="setMode('4C')" data-m="4C"><span class="mc">4C</span>4 Char</button>
    <button class="mode-btn" onclick="setMode('5L')" data-m="5L"><span class="mc">5L</span>5 Letter</button>
    <button class="mode-btn" onclick="setMode('5C')" data-m="5C"><span class="mc">5C</span>5 Char</button>
    <button class="mode-btn" onclick="setMode('5N')" data-m="5N"><span class="mc">5N</span>5 Number</button>
    <button class="mode-btn" onclick="setMode('6L')" data-m="6L"><span class="mc">6L</span>6 Letter</button>
    <button class="mode-btn" onclick="setMode('6C')" data-m="6C"><span class="mc">6C</span>6 Char</button>
    <button class="mode-btn" onclick="setMode('6N')" data-m="6N"><span class="mc">6N</span>6 Number</button>
  </div>

  <div class="stats-grid">
    <div class="stat"><div class="sl">Checked</div><div class="sv ca" id="sC">0</div></div>
    <div class="stat"><div class="sl">Available</div><div class="sv cg" id="sA">0</div></div>
    <div class="stat"><div class="sl">Hit Rate</div><div class="sv cb" id="sH">0.00%</div></div>
    <div class="stat"><div class="sl">Names / sec</div><div class="sv" id="sR">0.0</div></div>
  </div>

  <div class="batch-row">
    <div class="bi"><span>Batches</span><span class="pill pa" id="bB">0</span></div>
    <div class="bi"><span>Progress</span><span class="pill pb" id="bP">0 / 0</span></div>
    <div class="bi"><span>Runtime</span><span class="pill pa" id="bR">0s</span></div>
    <div class="prog-wrap"><div class="prog-bar" id="pgb"></div></div>
  </div>

  <div class="last-found" id="lf">
    <div>
      <div class="lf-lbl">Last found</div>
      <div class="lf-name" id="lfn">—</div>
    </div>
    <div class="lf-time" id="lft">—</div>
  </div>

  <div class="ctrl-row">
    <div class="cg"><label>Batch Size</label><input type="number" id="cnt" value="60" min="1" max="500"/></div>
    <div class="cg"><label>Delay (ms)</label><input type="number" id="dly" value="100" min="0" max="5000"/></div>
    <button class="btn btn-go" id="btnS" onclick="startScan()">Start</button>
    <button class="btn btn-stop" id="btnX" onclick="stopScan()" disabled>Stop</button>
  </div>

  <div class="feed-wrap">
    <div class="feed-hdr">
      <span class="feed-title">Live Feed</span>
      <span class="feed-meta" id="fc">0 results</span>
    </div>
    <div class="feed-body" id="fb">
      <div class="empty">start scanning to see results</div>
    </div>
  </div>
</div>
<script>
const MODES={'4L':{length:4,type:'letters'},'4C':{length:4,type:'mixed'},'5L':{length:5,type:'letters'},'5C':{length:5,type:'mixed'},'5N':{length:5,type:'numbers'},'6L':{length:6,type:'letters'},'6C':{length:6,type:'mixed'},'6N':{length:6,type:'numbers'}};
let mode='4L',scanning=false,t0=0,checked=0,avail=0,batches=0,feedCount=0,rt;
function setMode(m){mode=m;document.querySelectorAll('.mode-btn').forEach(b=>b.classList.toggle('active',b.dataset.m===m))}
function setStatus(s){document.getElementById('dot').className='dot'+(s==='scanning'?' on':'');document.getElementById('stxt').textContent=s}
function upStats(){
  document.getElementById('sC').textContent=checked;
  document.getElementById('sA').textContent=avail;
  document.getElementById('sH').textContent=checked>0?((avail/checked)*100).toFixed(2)+'%':'0.00%';
  document.getElementById('sR').textContent=t0>0?(checked/((Date.now()-t0)/1000)).toFixed(1):'0.0';
}
function upRuntime(){const s=Math.floor((Date.now()-t0)/1000),m=Math.floor(s/60);document.getElementById('bR').textContent=m>0?m+'m '+(s%60)+'s':s+'s'}
function showLast(u){document.getElementById('lf').classList.add('show');document.getElementById('lfn').textContent=u;document.getElementById('lft').textContent=new Date().toLocaleTimeString()}
function addItem(u,av,tp){
  const b=document.getElementById('fb');
  const e=b.querySelector('.empty');if(e)e.remove();
  feedCount++;document.getElementById('fc').textContent=feedCount+' results';
  const d=document.createElement('div');d.className='fi'+(av?' hit':'');
  d.innerHTML=`<span class="fu">${u}</span><span class="fm"><span class="tag ${av?'tag-av':'tag-tk'}">${av?'AVAILABLE':'taken'}</span><span>${tp}</span><span>${new Date().toLocaleTimeString()}</span></span>`;
  b.prepend(d);
}
async function startScan(){
  if(scanning)return;
  scanning=true;checked=0;avail=0;batches=0;feedCount=0;t0=Date.now();
  document.getElementById('fb').innerHTML='<div class="empty">scanning...</div>';
  document.getElementById('fc').textContent='0 results';
  document.getElementById('lf').classList.remove('show');
  document.getElementById('btnS').disabled=true;
  document.getElementById('btnX').disabled=false;
  setStatus('scanning');rt=setInterval(upRuntime,1000);
  const count=parseInt(document.getElementById('cnt').value)||60;
  const delay=parseInt(document.getElementById('dly').value)||100;
  const cfg=MODES[mode];
  batches++;document.getElementById('bB').textContent=batches;
  for(let i=0;i<count;i++){
    if(!scanning)break;
    document.getElementById('bP').textContent=(i+1)+' / '+count;
    document.getElementById('pgb').style.width=((i+1)/count*100)+'%';
    try{
      const r=await fetch('/api/check',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:'generate',count:1,length:cfg.length,username_type:cfg.type,scan_type:mode})});
      const d=await r.json();
      if(d.results&&d.results.length>0){const it=d.results[0];checked++;if(it.available){avail++;showLast(it.username);}addItem(it.username,it.available,mode);upStats();}
    }catch(e){console.error(e)}
    await new Promise(r=>setTimeout(r,delay));
  }
  scanning=false;clearInterval(rt);
  document.getElementById('btnS').disabled=false;
  document.getElementById('btnX').disabled=true;
  document.getElementById('pgb').style.width='100%';
  setStatus('done');
}
function stopScan(){scanning=false;clearInterval(rt);document.getElementById('btnS').disabled=false;document.getElementById('btnX').disabled=true;setStatus('stopped')}
</script>
</body>
</html>"""


ADMIN_DASHBOARD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>RBXScan — Admin</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Syne:wght@400;600;700&display=swap" rel="stylesheet"/>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#060a12;--panel:#0d1421;--border:rgba(255,255,255,0.07);
  --accent:#6c63ff;--green:#00e5a0;--amber:#ffb347;--red:#ff6584;
  --text:#e8eaf6;--muted:#6b7280;
  --mono:'JetBrains Mono',monospace;--sans:'Syne',sans-serif
}
body{background:var(--bg);color:var(--text);font-family:var(--sans);min-height:100vh}
.app{max-width:1100px;margin:0 auto;padding:24px 16px}
.topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:32px;padding-bottom:16px;border-bottom:1px solid var(--border)}
.logo{font-size:20px;font-weight:700}.logo span{color:var(--accent)}
.logo-sub{font-size:12px;color:var(--muted);font-weight:400;margin-left:8px;font-family:var(--mono)}
.nav-link{color:var(--muted);text-decoration:none;font-size:12px;font-family:var(--mono);margin-left:20px;transition:color .2s}.nav-link:hover{color:var(--text)}
.stats-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:24px}
.stat{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:16px}
.sl{font-size:10px;color:var(--muted);font-family:var(--mono);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
.sv{font-size:26px;font-weight:700;font-family:var(--mono)}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:22px;margin-bottom:20px}
.panel-title{font-size:15px;font-weight:700;margin-bottom:6px}
.panel-sub{font-size:12px;color:var(--muted);font-family:var(--mono);margin-bottom:18px}
/* toggle */
.toggle-row{display:flex;align-items:center;justify-content:space-between}
.toggle{position:relative;width:48px;height:26px;cursor:pointer;flex-shrink:0}
.toggle input{opacity:0;width:0;height:0}
.slider{position:absolute;inset:0;background:rgba(255,255,255,0.1);border-radius:26px;transition:.3s}
.slider:before{content:'';position:absolute;width:20px;height:20px;left:3px;bottom:3px;background:#fff;border-radius:50%;transition:.3s}
input:checked+.slider{background:var(--green)}
input:checked+.slider:before{transform:translateX(22px)}
/* whitelist */
.wl-form{display:grid;grid-template-columns:1fr 1fr auto;gap:10px;margin-bottom:16px;align-items:end}
.fg label{font-size:10px;color:var(--muted);font-family:var(--mono);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:6px}
input[type=text],input[type=number]{width:100%;padding:10px 13px;border-radius:9px;border:1px solid var(--border);background:#080c14;color:var(--text);font-family:var(--mono);font-size:13px;outline:none}
input:focus{border-color:var(--accent)}
.btn{padding:10px 18px;border-radius:9px;border:none;font-family:var(--sans);font-size:13px;font-weight:700;cursor:pointer;transition:all .2s;white-space:nowrap}
.btn-accent{background:var(--accent);color:#fff}.btn-accent:hover{filter:brightness(1.1)}
.btn-red{background:rgba(255,101,132,0.1);color:var(--red);border:1px solid rgba(255,101,132,0.2)}.btn-red:hover{background:rgba(255,101,132,0.2)}
.btn-sm{padding:5px 12px;font-size:11px;border-radius:7px}
.wl-table,.names-table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12px}
.wl-table th,.names-table th{text-align:left;padding:8px 12px;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid var(--border)}
.wl-table td,.names-table td{padding:10px 12px;border-bottom:1px solid rgba(255,255,255,0.035)}
.wl-table tr:hover td,.names-table tr:hover td{background:rgba(255,255,255,0.02)}
.id-badge{background:rgba(108,99,255,0.12);color:var(--accent);padding:3px 8px;border-radius:5px;font-size:11px}
.type-badge{background:rgba(108,99,255,0.12);color:var(--accent);padding:3px 8px;border-radius:5px;font-size:10px}
.msg{font-size:12px;font-family:var(--mono);margin-top:10px;min-height:18px}
.msg.ok{color:var(--green)}.msg.err{color:var(--red)}
/* webhooks */
.wh-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:16px}
.wh-item label{font-size:10px;color:var(--muted);font-family:var(--mono);text-transform:uppercase;letter-spacing:1px;display:block;margin-bottom:5px}
/* filters */
.filters{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.fbtn{padding:6px 14px;border-radius:8px;border:1px solid var(--border);background:rgba(255,255,255,0.03);color:var(--muted);cursor:pointer;font-family:var(--mono);font-size:11px;transition:all .15s}
.fbtn.active{border-color:var(--accent);background:rgba(108,99,255,0.1);color:var(--accent)}
.empty-row{text-align:center;padding:20px;color:var(--muted);font-size:12px}
</style>
</head>
<body>
<div class="app">
  <div class="topbar">
    <div class="logo">RBX<span>Scan</span><span class="logo-sub">admin</span></div>
    <div>
      <a href="/" class="nav-link">Scanner</a>
      <a href="/logout" class="nav-link">Logout</a>
    </div>
  </div>

  <div class="stats-grid">
    <div class="stat"><div class="sl">Total Found</div><div class="sv" id="tot">0</div></div>
    <div class="stat"><div class="sl">Today</div><div class="sv" id="tod">0</div></div>
    <div class="stat"><div class="sl">4 Letter</div><div class="sv" id="s4l">0</div></div>
    <div class="stat"><div class="sl">5 Letter</div><div class="sv" id="s5l">0</div></div>
  </div>

  <!-- Access Control -->
  <div class="panel">
    <div class="panel-title">Access Control</div>
    <div class="panel-sub">Toggle between open access (anyone with Discord) and whitelist-only mode.</div>
    <div class="toggle-row">
      <div>
        <div style="font-size:14px;font-weight:600;margin-bottom:4px" id="accessLabel">Open Access</div>
        <div style="font-size:12px;color:var(--muted);font-family:var(--mono)" id="accessDesc">Anyone who authorizes with Discord can log in.</div>
      </div>
      <label class="toggle">
        <input type="checkbox" id="openToggle" onchange="toggleAccess()"/>
        <span class="slider"></span>
      </label>
    </div>
    <div class="msg" id="accessMsg"></div>
  </div>

  <!-- Whitelist -->
  <div class="panel">
    <div class="panel-title">Discord Whitelist</div>
    <div class="panel-sub">Add Discord user IDs that are allowed when whitelist mode is active.</div>
    <div class="wl-form">
      <div class="fg">
        <label>Discord ID</label>
        <input type="text" id="wlId" placeholder="e.g. 1002813531420373063"/>
      </div>
      <div class="fg">
        <label>Nickname</label>
        <input type="text" id="wlNick" placeholder="e.g. John"/>
      </div>
      <button class="btn btn-accent" onclick="addUser()" style="margin-top:auto">Add User</button>
    </div>
    <div class="msg" id="wlMsg"></div>
    <table class="wl-table">
      <thead><tr><th>Discord ID</th><th>Nickname</th><th>Added</th><th></th></tr></thead>
      <tbody id="wlBody"></tbody>
    </table>
  </div>

  <!-- Webhooks -->
  <div class="panel">
    <div class="panel-title">Webhook Settings</div>
    <div class="panel-sub">Discord webhook URLs per scan mode. Fires when an available username is found.</div>
    <div class="wh-grid">
      <div class="wh-item"><label>4L — 4 Letter</label><input type="text" id="wh_4L" placeholder="https://discord.com/api/webhooks/..."/></div>
      <div class="wh-item"><label>4C — 4 Char</label><input type="text" id="wh_4C" placeholder="https://discord.com/api/webhooks/..."/></div>
      <div class="wh-item"><label>5L — 5 Letter</label><input type="text" id="wh_5L" placeholder="https://discord.com/api/webhooks/..."/></div>
      <div class="wh-item"><label>5C — 5 Char</label><input type="text" id="wh_5C" placeholder="https://discord.com/api/webhooks/..."/></div>
      <div class="wh-item"><label>5N — 5 Number</label><input type="text" id="wh_5N" placeholder="https://discord.com/api/webhooks/..."/></div>
      <div class="wh-item"><label>6L — 6 Letter</label><input type="text" id="wh_6L" placeholder="https://discord.com/api/webhooks/..."/></div>
      <div class="wh-item"><label>6C — 6 Char</label><input type="text" id="wh_6C" placeholder="https://discord.com/api/webhooks/..."/></div>
      <div class="wh-item"><label>6N — 6 Number</label><input type="text" id="wh_6N" placeholder="https://discord.com/api/webhooks/..."/></div>
    </div>
    <button class="btn btn-accent" onclick="saveWebhooks()">Save Webhooks</button>
    <div class="msg" id="whMsg"></div>
  </div>

  <!-- Names -->
  <div class="panel">
    <div class="panel-title">Available Usernames</div>
    <div class="filters">
      <button class="fbtn active" onclick="filterNames('All',this)">All</button>
      <button class="fbtn" onclick="filterNames('4L',this)">4L</button>
      <button class="fbtn" onclick="filterNames('4C',this)">4C</button>
      <button class="fbtn" onclick="filterNames('5L',this)">5L</button>
      <button class="fbtn" onclick="filterNames('5C',this)">5C</button>
      <button class="fbtn" onclick="filterNames('5N',this)">5N</button>
      <button class="fbtn" onclick="filterNames('6L',this)">6L</button>
      <button class="fbtn" onclick="filterNames('6C',this)">6C</button>
      <button class="fbtn" onclick="filterNames('6N',this)">6N</button>
    </div>
    <table class="names-table">
      <thead><tr><th>Username</th><th>Type</th><th>Found At</th></tr></thead>
      <tbody id="namesBody"></tbody>
    </table>
  </div>
</div>

<script>
let nameFilter='All';

async function loadStats(){
  const r=await fetch('/api/stats');const d=await r.json();
  document.getElementById('tot').textContent=d.total;
  document.getElementById('tod').textContent=d.today;
  document.getElementById('s4l').textContent=d.by_type['4L']||0;
  document.getElementById('s5l').textContent=d.by_type['5L']||0;
}

async function loadSettings(){
  const r=await fetch('/api/settings');const d=await r.json();
  const toggle=document.getElementById('openToggle');
  toggle.checked=d.open_access;
  updateAccessLabel(d.open_access);
}

function updateAccessLabel(open){
  document.getElementById('accessLabel').textContent=open?'Open Access':'Whitelist Only';
  document.getElementById('accessDesc').textContent=open?'Anyone who authorizes with Discord can log in.':'Only whitelisted Discord IDs can log in.';
}

async function toggleAccess(){
  const v=document.getElementById('openToggle').checked;
  const r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({open_access:v})});
  const d=await r.json();
  updateAccessLabel(d.open_access);
  const msg=document.getElementById('accessMsg');
  msg.className='msg ok';
  msg.textContent=d.open_access?'Open access enabled.':'Whitelist mode enabled.';
  setTimeout(()=>msg.textContent='',3000);
}

async function loadWhitelist(){
  const r=await fetch('/api/whitelist');const rows=await r.json();
  const tb=document.getElementById('wlBody');
  if(!rows.length){tb.innerHTML='<tr><td colspan="4" class="empty-row">No users whitelisted yet.</td></tr>';return;}
  tb.innerHTML=rows.map(u=>`
    <tr>
      <td><span class="id-badge">${u.discord_id}</span></td>
      <td>${u.nickname}</td>
      <td style="color:var(--muted)">${new Date(u.added_at).toLocaleString()}</td>
      <td><button class="btn btn-red btn-sm" onclick="removeUser('${u.discord_id}')">Remove</button></td>
    </tr>`).join('');
}

async function addUser(){
  const id=document.getElementById('wlId').value.trim();
  const nick=document.getElementById('wlNick').value.trim();
  const msg=document.getElementById('wlMsg');
  if(!id){msg.className='msg err';msg.textContent='Discord ID is required.';return;}
  const r=await fetch('/api/whitelist/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({discord_id:id,nickname:nick||id})});
  const d=await r.json();
  if(d.status==='added'){
    msg.className='msg ok';msg.textContent='User added successfully.';
    document.getElementById('wlId').value='';document.getElementById('wlNick').value='';
    loadWhitelist();
  } else {
    msg.className='msg err';msg.textContent='User already exists in whitelist.';
  }
  setTimeout(()=>msg.textContent='',3000);
}

async function removeUser(id){
  await fetch('/api/whitelist/remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({discord_id:id})});
  loadWhitelist();
}

async function loadWebhooks(){
  const r=await fetch('/api/webhooks');const d=await r.json();
  ['4L','4C','5L','5C','5N','6L','6C','6N'].forEach(k=>{const el=document.getElementById(`wh_${k}`);if(el)el.value=d[k]||''});
}

async function saveWebhooks(){
  const payload={};
  ['4L','4C','5L','5C','5N','6L','6C','6N'].forEach(k=>{payload[k]=document.getElementById(`wh_${k}`).value});
  await fetch('/api/webhooks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  const msg=document.getElementById('whMsg');msg.className='msg ok';msg.textContent='Webhooks saved.';
  setTimeout(()=>msg.textContent='',3000);
}

async function loadNames(){
  const ep=nameFilter==='All'?'/api/names':`/api/names?type=${nameFilter}`;
  const r=await fetch(ep);const names=await r.json();
  document.getElementById('namesBody').innerHTML=names.length
    ?names.map(n=>`<tr><td>${n[0]}</td><td><span class="type-badge">${n[1]}</span></td><td style="color:var(--muted)">${new Date(n[2]).toLocaleString()}</td></tr>`).join('')
    :'<tr><td colspan="3" class="empty-row">No names found yet.</td></tr>';
}

function filterNames(f,btn){
  nameFilter=f;
  document.querySelectorAll('.fbtn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  loadNames();
}

setInterval(loadStats,5000);
setInterval(loadNames,8000);
loadStats();loadSettings();loadWhitelist();loadWebhooks();loadNames();
</script>
</body>
</html>"""


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '').strip()
        if u == AUTH_USERNAME and p == AUTH_PASSWORD:
            session['logged_in'] = True
            session['auth_method'] = 'local'
            return redirect(url_for('index'))
        error = 'Invalid username or password.'
    discord_enabled = bool(DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET)
    return render_template_string(LOGIN_PAGE, error=error, discord_enabled=discord_enabled)


@app.route('/discord_login')
def discord_login():
    if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_SECRET:
        return redirect(url_for('login'))
    params = {
        'client_id': DISCORD_CLIENT_ID,
        'redirect_uri': DISCORD_REDIRECT_URI,
        'response_type': 'code',
        'scope': DISCORD_SCOPE,
        'prompt': 'consent'
    }
    return redirect(f"{DISCORD_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}")


@app.route('/discord/callback')
def discord_callback():
    discord_enabled = bool(DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET)

    error = request.args.get('error')
    if error:
        return render_template_string(LOGIN_PAGE, error=f'Discord error: {error}', discord_enabled=discord_enabled)

    code = request.args.get('code')
    if not code:
        return redirect(url_for('login'))

    token_resp = requests.post(
        DISCORD_TOKEN_URL,
        data={
            'client_id': DISCORD_CLIENT_ID,
            'client_secret': DISCORD_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': DISCORD_REDIRECT_URI,
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=10
    )

    if token_resp.status_code != 200:
        return render_template_string(LOGIN_PAGE,
            error=f'Token exchange failed ({token_resp.status_code}). Check your client secret.',
            discord_enabled=discord_enabled)

    access_token = token_resp.json().get('access_token')
    if not access_token:
        return render_template_string(LOGIN_PAGE, error='No access token received.', discord_enabled=discord_enabled)

    user_resp = requests.get(DISCORD_API_ME,
        headers={'Authorization': f'Bearer {access_token}'}, timeout=10)
    if user_resp.status_code != 200:
        return render_template_string(LOGIN_PAGE, error='Could not fetch Discord user info.', discord_enabled=discord_enabled)

    user_data = user_resp.json()
    discord_id = user_data.get('id')
    if not discord_id:
        return render_template_string(LOGIN_PAGE, error='Discord user data missing.', discord_enabled=discord_enabled)

    open_access = get_setting('open_access') == '1'
    if not open_access and not is_whitelisted(discord_id):
        return render_template_string(LOGIN_PAGE,
            error='You are not whitelisted. Contact the admin to get access.',
            discord_enabled=discord_enabled)

    session['logged_in'] = True
    session['auth_method'] = 'discord'
    session['discord_token'] = access_token
    session['discord_user'] = {
        'id': discord_id,
        'username': user_data.get('username'),
        'global_name': user_data.get('global_name'),
        'discriminator': user_data.get('discriminator'),
        'avatar': user_data.get('avatar'),
    }
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
def index():
    return render_template_string(USER_DASHBOARD)


@app.route('/admin')
def admin():
    return render_template_string(ADMIN_DASHBOARD)


@app.route('/api/me')
def api_me():
    if not is_authenticated():
        return jsonify(error='Not logged in'), 401
    if session.get('auth_method') != 'discord':
        return jsonify(error='Not a Discord session'), 403
    user = session.get('discord_user', {})
    uid = user.get('id')
    avatar = user.get('avatar')
    return jsonify({
        'id': uid,
        'username': user.get('username'),
        'global_name': user.get('global_name'),
        'avatar_url': f'https://cdn.discordapp.com/avatars/{uid}/{avatar}.png' if avatar else None,
    })


@app.route('/api/stats')
def api_stats():
    return jsonify(get_stats())


@app.route('/api/names')
def api_names():
    t = request.args.get('type')
    return jsonify(get_names_by_type(t) if t else get_all_names())


@app.route('/api/webhooks', methods=['GET', 'POST'])
def api_webhooks():
    if request.method == 'GET':
        return jsonify(load_webhooks())
    payload = request.get_json(force=True)
    webhooks = {k: payload.get(k, '') for k in WEBHOOK_KEYS}
    save_webhooks(webhooks)
    return jsonify({'status': 'saved'})


@app.route('/api/whitelist', methods=['GET'])
def api_whitelist_get():
    rows = get_whitelist()
    return jsonify([{'discord_id': r[0], 'nickname': r[1], 'added_at': r[2]} for r in rows])


@app.route('/api/whitelist/add', methods=['POST'])
def api_whitelist_add():
    payload = request.get_json(force=True)
    discord_id = payload.get('discord_id', '').strip()
    nickname = payload.get('nickname', '').strip()
    if not discord_id:
        return jsonify({'status': 'error', 'message': 'Discord ID required'}), 400
    ok = add_to_whitelist(discord_id, nickname or discord_id)
    return jsonify({'status': 'added' if ok else 'exists'})


@app.route('/api/whitelist/remove', methods=['POST'])
def api_whitelist_remove():
    payload = request.get_json(force=True)
    discord_id = payload.get('discord_id', '').strip()
    if not discord_id:
        return jsonify({'status': 'error'}), 400
    remove_from_whitelist(discord_id)
    return jsonify({'status': 'removed'})


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    if request.method == 'GET':
        return jsonify({'open_access': get_setting('open_access') == '1'})
    payload = request.get_json(force=True)
    if 'open_access' in payload:
        set_setting('open_access', '1' if payload['open_access'] else '0')
    return jsonify({'status': 'saved', 'open_access': get_setting('open_access') == '1'})


@app.route('/api/check', methods=['POST'])
def api_check():
    payload = request.get_json(force=True)
    mode = payload.get('mode', 'single')
    try:
        if mode == 'single':
            result = checker.check_username(payload.get('username', '').strip())
            return jsonify(result=result)
        if mode == 'multiple':
            results = checker.check_multiple([u.strip() for u in payload.get('usernames', []) if u.strip()])
            return jsonify(results=results)
        if mode == 'generate':
            count = int(payload.get('count', 1))
            length = int(payload.get('length', 6))
            username_type = payload.get('username_type', 'mixed')
            if count <= 0 or length < checker.USERNAME_MIN_LENGTH or length > checker.USERNAME_MAX_LENGTH:
                return jsonify(error='Invalid count or length'), 400
            usernames = checker.generate_batch_usernames(count, length, username_type)
            results = checker.check_multiple(usernames)
            for result in results:
                if result.get('available'):
                    scan_type = payload.get('scan_type', username_type)
                    add_to_db(result['username'], scan_type)
                    send_webhook(result['username'], scan_type)
            return jsonify(results=results)
        return jsonify(error='Invalid mode'), 400
    except Exception as e:
        return jsonify(error=str(e)), 500


def open_browser():
    webbrowser.open('http://127.0.0.1:5000')


init_db()

if __name__ == '__main__':
    if os.environ.get('FLASK_RUN_FROM_CLI') is None:
        threading.Timer(1.0, open_browser).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
