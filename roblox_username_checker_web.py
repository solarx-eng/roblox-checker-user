import os
import json
import threading
import webbrowser
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from roblox_username_checker import RobloxUsernameChecker
import sqlite3

app = Flask(__name__)
checker = RobloxUsernameChecker(rate_limit_delay=0.2)

# Initialize database
DB_FILE = 'usernames.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS available_names
                 (id INTEGER PRIMARY KEY, username TEXT UNIQUE, type TEXT, found_at TIMESTAMP, found_by TEXT)''')
    conn.commit()
    conn.close()

def add_to_db(username, username_type, found_by='scanner'):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT INTO available_names (username, type, found_at, found_by) VALUES (?, ?, ?, ?)',
                  (username, username_type, datetime.now(), found_by))
        conn.commit()
        conn.close()
        return True
    except:
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
    c.execute('SELECT username, type, found_at FROM available_names WHERE type = ? ORDER BY found_at DESC', (username_type,))
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
    c.execute('SELECT COUNT(DISTINCT DATE(found_at)) FROM available_names')
    today = c.fetchone()[0]
    conn.close()
    return {'total': total, 'by_type': by_type, 'today': today}

def send_webhook(username, username_type):
    webhook_url = os.environ.get(f'WEBHOOK_{username_type.upper()}')
    if not webhook_url:
        return
    try:
        import requests
        requests.post(webhook_url, json={
            'username': username,
            'type': username_type,
            'timestamp': datetime.now().isoformat()
        })
    except:
        pass

init_db()

USER_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Roblox Username Checker</title>
    <style>
        :root {
            --bg: #0b1120;
            --panel: rgba(15, 23, 42, 0.95);
            --panel-border: rgba(148, 163, 184, 0.12);
            --text: #e2e8f0;
            --muted: #94a3b8;
            --accent: #8b5cf6;
            --accent-strong: #7c3aed;
            --success: #22c55e;
        }
        * { box-sizing: border-box; }
        body { margin: 0; min-height: 100vh; font-family: Inter, system-ui, sans-serif; background: linear-gradient(180deg, #090c18 0%, #060913 100%); color: var(--text); }
        .app { width: min(1200px, 100%); margin: 0 auto; padding: 24px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
        .header h1 { margin: 0; font-size: 2rem; }
        .nav-links a { color: var(--accent); margin-left: 24px; text-decoration: none; font-size: 0.95rem; }
        .panel { background: var(--panel); border: 1px solid var(--panel-border); border-radius: 24px; padding: 24px; margin-bottom: 20px; }
        .modes { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }
        .mode-btn { padding: 16px; border-radius: 16px; background: rgba(148, 163, 184, 0.1); border: 1px solid transparent; color: var(--text); cursor: pointer; transition: all .2s; }
        .mode-btn.active { background: rgba(139, 92, 246, 0.2); border-color: var(--accent); }
        .mode-btn:hover { transform: translateY(-2px); }
        .controls { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 16px; }
        input { width: 100%; padding: 12px; border-radius: 12px; border: 1px solid rgba(148, 163, 184, 0.2); background: rgba(15, 23, 42, 0.8); color: var(--text); }
        button { background: linear-gradient(135deg, #8b5cf6, #4338ca); color: white; border: none; padding: 14px 24px; border-radius: 14px; cursor: pointer; font-weight: 600; }
        button:hover { filter: brightness(1.1); }
        .feed { display: flex; flex-direction: column; gap: 8px; max-height: 400px; overflow-y: auto; }
        .feed-item { padding: 10px; background: rgba(148, 163, 184, 0.08); border-radius: 10px; display: flex; justify-content: space-between; }
        .feed-item.available { border-left: 3px solid var(--success); }
        .stat-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }
        .stat-card { background: rgba(139, 92, 246, 0.1); padding: 16px; border-radius: 14px; }
        .stat-card strong { display: block; font-size: 1.5rem; }
        @media(max-width: 900px) { .modes { grid-template-columns: repeat(2, 1fr); } .controls { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="app">
        <div class="header">
            <h1>🔍 Roblox Username Checker</h1>
            <div class="nav-links">
                <a href="/">Scanner</a>
                <a href="/admin">Admin Dashboard</a>
            </div>
        </div>

        <div class="panel">
            <h2>Select Mode</h2>
            <div class="modes" id="modeGrid">
                <button class="mode-btn active" onclick="selectMode('4L')" data-mode="4L">4L - 4 Letter</button>
                <button class="mode-btn" onclick="selectMode('4C')" data-mode="4C">4C - 4 Char</button>
                <button class="mode-btn" onclick="selectMode('5L')" data-mode="5L">5L - 5 Letter</button>
                <button class="mode-btn" onclick="selectMode('5C')" data-mode="5C">5C - 5 Char</button>
                <button class="mode-btn" onclick="selectMode('5N')" data-mode="5N">5N - 5 Number</button>
                <button class="mode-btn" onclick="selectMode('6L')" data-mode="6L">6L - 6 Letter</button>
                <button class="mode-btn" onclick="selectMode('6C')" data-mode="6C">6C - 6 Char</button>
                <button class="mode-btn" onclick="selectMode('6N')" data-mode="6N">6N - 6 Number</button>
            </div>
        </div>

        <div class="panel">
            <div class="stat-row">
                <div class="stat-card"><strong id="modeLabel">4L</strong><span>Selected Mode</span></div>
                <div class="stat-card"><strong id="checked">0</strong><span>Checked</span></div>
                <div class="stat-card"><strong id="available">0</strong><span>Available</span></div>
            </div>

            <div class="controls">
                <input id="count" type="number" placeholder="How many" value="60" min="1" max="500" />
                <input id="delay" type="number" placeholder="Delay (ms)" value="100" min="0" max="5000" />
                <button onclick="startScan()">Start Scanning</button>
            </div>

            <h3>Live Feed</h3>
            <div class="feed" id="feed"></div>
        </div>
    </div>

    <script>
        const modes = { '4L': { length: 4, type: 'letters' }, '4C': { length: 4, type: 'mixed' }, '5L': { length: 5, type: 'letters' }, '5C': { length: 5, type: 'mixed' }, '5N': { length: 5, type: 'numbers' }, '6L': { length: 6, type: 'letters' }, '6C': { length: 6, type: 'mixed' }, '6N': { length: 6, type: 'numbers' } };
        let selectedMode = '4L';
        let scanning = false;

        function selectMode(id) {
            selectedMode = id;
            document.getElementById('modeLabel').innerText = id;
            document.querySelectorAll('.mode-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === id));
        }

        async function startScan() {
            if (scanning) return;
            scanning = true;
            const count = Number(document.getElementById('count').value) || 60;
            const delay = Number(document.getElementById('delay').value) || 100;
            const config = modes[selectedMode];
            document.getElementById('feed').innerHTML = '';
            let found = 0;
            let checked = 0;

            for (let i = 0; i < count; i++) {
                try {
                    const res = await fetch('/api/check', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: 'generate', count: 1, length: config.length, username_type: config.type, scan_type: selectedMode }) });
                    const data = await res.json();
                    if (data.results && data.results[0]) {
                        const item = data.results[0];
                        checked++;
                        if (item.available) {
                            found++;
                            const div = document.createElement('div');
                            div.className = 'feed-item available';
                            div.innerHTML = `<strong>${item.username}</strong><span style="color: #22c55e;">AVAILABLE</span>`;
                            document.getElementById('feed').prepend(div);
                        }
                    }
                } catch (e) { }
                document.getElementById('checked').innerText = checked;
                document.getElementById('available').innerText = found;
                await new Promise(r => setTimeout(r, delay));
            }
            scanning = false;
        }
    </script>
</body>
</html>
"""

ADMIN_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Admin Dashboard</title>
    <style>
        :root {
            --bg: #0b1120;
            --panel: rgba(15, 23, 42, 0.95);
            --panel-border: rgba(148, 163, 184, 0.12);
            --text: #e2e8f0;
            --muted: #94a3b8;
            --accent: #8b5cf6;
            --success: #22c55e;
        }
        * { box-sizing: border-box; }
        body { margin: 0; min-height: 100vh; font-family: Inter, system-ui, sans-serif; background: linear-gradient(180deg, #090c18 0%, #060913 100%); color: var(--text); }
        .app { width: min(1400px, 100%); margin: 0 auto; padding: 24px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
        .header h1 { margin: 0; font-size: 2rem; }
        .nav-links a { color: var(--accent); margin-left: 24px; text-decoration: none; }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
        .stat { background: var(--panel); padding: 20px; border-radius: 16px; border: 1px solid var(--panel-border); }
        .stat strong { display: block; font-size: 2rem; margin-bottom: 8px; }
        .stat span { color: var(--muted); font-size: 0.9rem; }
        .panel { background: var(--panel); border: 1px solid var(--panel-border); border-radius: 16px; padding: 20px; margin-bottom: 20px; }
        .filters { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
        .filter-btn { padding: 10px 16px; border-radius: 10px; border: 1px solid rgba(148, 163, 184, 0.2); background: rgba(148, 163, 184, 0.1); color: var(--text); cursor: pointer; }
        .filter-btn.active { background: rgba(139, 92, 246, 0.2); border-color: var(--accent); }
        .names-table { width: 100%; border-collapse: collapse; }
        .names-table tr { border-bottom: 1px solid rgba(148, 163, 184, 0.1); }
        .names-table td { padding: 12px; }
        .names-table tr:hover { background: rgba(148, 163, 184, 0.05); }
        .type-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; background: rgba(139, 92, 246, 0.2); font-size: 0.85rem; }
    </style>
</head>
<body>
    <div class="app">
        <div class="header">
            <h1>👨‍💼 Admin Dashboard</h1>
            <div class="nav-links">
                <a href="/">← Back to Scanner</a>
            </div>
        </div>

        <div class="stats">
            <div class="stat">
                <strong id="totalCount">0</strong>
                <span>Total Names Found</span>
            </div>
            <div class="stat">
                <strong id="todayCount">0</strong>
                <span>Found Today</span>
            </div>
            <div class="stat">
                <strong id="type4lCount">0</strong>
                <span>4 Letter</span>
            </div>
            <div class="stat">
                <strong id="type5lCount">0</strong>
                <span>5 Letter</span>
            </div>
        </div>

        <div class="panel">
            <h2>Available Usernames</h2>
            <div class="filters">
                <button class="filter-btn active" onclick="filterType('All')">All</button>
                <button class="filter-btn" onclick="filterType('4L')">4L</button>
                <button class="filter-btn" onclick="filterType('5L')">5L</button>
                <button class="filter-btn" onclick="filterType('6L')">6L</button>
                <button class="filter-btn" onclick="filterType('4C')">4C</button>
                <button class="filter-btn" onclick="filterType('5C')">5C</button>
            </div>
            <table class="names-table">
                <thead>
                    <tr>
                        <td><strong>Username</strong></td>
                        <td><strong>Type</strong></td>
                        <td><strong>Found</strong></td>
                    </tr>
                </thead>
                <tbody id="namesBody"></tbody>
            </table>
        </div>
    </div>

    <script>
        let currentFilter = 'All';

        async function loadStats() {
            const res = await fetch('/api/stats');
            const data = await res.json();
            document.getElementById('totalCount').innerText = data.total;
            document.getElementById('todayCount').innerText = data.today;
            document.getElementById('type4lCount').innerText = data.by_type['4L'] || 0;
            document.getElementById('type5lCount').innerText = data.by_type['5L'] || 0;
        }

        async function loadNames() {
            const endpoint = currentFilter === 'All' ? '/api/names' : `/api/names?type=${currentFilter}`;
            const res = await fetch(endpoint);
            const names = await res.json();
            const tbody = document.getElementById('namesBody');
            tbody.innerHTML = names.map(n => `<tr><td>${n[0]}</td><td><span class="type-badge">${n[1]}</span></td><td>${new Date(n[2]).toLocaleString()}</td></tr>`).join('');
        }

        function filterType(type) {
            currentFilter = type;
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            loadNames();
        }

        setInterval(loadStats, 5000);
        setInterval(loadNames, 5000);
        loadStats();
        loadNames();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(USER_DASHBOARD)

@app.route('/admin')
def admin():
    return render_template_string(ADMIN_DASHBOARD)

@app.route('/api/stats')
def api_stats():
    stats = get_stats()
    return jsonify(stats)

@app.route('/api/names')
def api_names():
    username_type = request.args.get('type')
    if username_type:
        names = get_names_by_type(username_type)
    else:
        names = get_all_names()
    return jsonify(names)

@app.route('/api/check', methods=['POST'])
def api_check():
    payload = request.get_json(force=True)
    mode = payload.get('mode', 'single')

    try:
        if mode == 'single':
            username = payload.get('username', '').strip()
            result = checker.check_username(username)
            return jsonify(result=result)

        if mode == 'multiple':
            usernames = payload.get('usernames', [])
            results = checker.check_multiple([u.strip() for u in usernames if u.strip()])
            return jsonify(results=results)

        if mode == 'generate':
            count = int(payload.get('count', 1))
            length = int(payload.get('length', 6))
            username_type = payload.get('username_type', 'mixed')

            if count <= 0 or length < checker.USERNAME_MIN_LENGTH or length > checker.USERNAME_MAX_LENGTH:
                return jsonify(error='Invalid count or length'), 400

            usernames = checker.generate_batch_usernames(count, length, username_type)
            results = checker.check_multiple(usernames)
            
            # Store available usernames and send webhooks
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

if __name__ == '__main__':
    if os.environ.get('FLASK_RUN_FROM_CLI') is None:
        threading.Timer(1.0, open_browser).start()

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
