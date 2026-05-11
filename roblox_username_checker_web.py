import os
import threading
import webbrowser
from flask import Flask, request, jsonify, render_template_string
from roblox_username_checker import RobloxUsernameChecker

app = Flask(__name__)
checker = RobloxUsernameChecker(rate_limit_delay=0.3)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Roblox Username Checker</title>
    <style>
        :root {
            color-scheme: dark;
            --bg: #0b1120;
            --panel: rgba(15, 23, 42, 0.95);
            --panel-border: rgba(148, 163, 184, 0.12);
            --text: #e2e8f0;
            --muted: #94a3b8;
            --accent: #8b5cf6;
            --accent-strong: #7c3aed;
            --success: #22c55e;
            --warning: #f59e0b;
            --danger: #ef4444;
        }

        * { box-sizing: border-box; }
        body { margin: 0; min-height: 100vh; font-family: Inter, system-ui, sans-serif; background: radial-gradient(circle at top, rgba(99, 102, 241, 0.2), transparent 30%), linear-gradient(180deg, #090c18 0%, #060913 100%); color: var(--text); }
        .app-shell { width: min(1180px, 100%); margin: 0 auto; padding: 24px 18px 32px; }
        .page-header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 26px; }
        .page-header h1 { margin: 0; font-size: clamp(2rem, 2.5vw, 2.6rem); letter-spacing: -0.03em; }
        .page-header p { margin: 0; color: var(--muted); max-width: 620px; }
        .panel { background: var(--panel); border: 1px solid var(--panel-border); border-radius: 24px; box-shadow: 0 20px 80px rgba(0,0,0,0.28); }
        .section { padding: 24px; }
        .modes-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 18px; }
        .mode-card { cursor: pointer; border-radius: 20px; padding: 22px 18px; background: rgba(15, 23, 42, 0.75); border: 1px solid transparent; transition: transform .18s ease, border-color .18s ease, background .18s ease; }
        .mode-card:hover { transform: translateY(-3px); border-color: rgba(139, 92, 246, 0.48); }
        .mode-card.active { background: linear-gradient(135deg, rgba(139,92,246,0.22), rgba(79,70,229,0.16)); border-color: rgba(139, 92, 246, 0.9); }
        .mode-card span { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; background: rgba(148, 163, 184, 0.12); border-radius: 999px; margin-bottom: 12px; color: var(--accent); font-weight: 700; }
        .mode-card h3 { margin: 0 0 8px; font-size: 1rem; }
        .mode-card p { margin: 0; color: var(--muted); font-size: 0.92rem; }
        .hero-card { display: grid; grid-template-columns: 1fr 1.2fr; gap: 20px; }
        .hero-card .hero-stat { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-bottom: 22px; }
        .stat-chip { background: rgba(148, 163, 184, 0.08); border: 1px solid rgba(148, 163, 184, 0.08); border-radius: 18px; padding: 16px; }
        .stat-chip strong { display: block; font-size: 1.13rem; margin-bottom: 6px; }
        .stat-chip span { color: var(--muted); font-size: 0.92rem; }
        .live-panel { display: grid; grid-template-columns: 1fr; gap: 20px; }
        .control-panel { display: grid; gap: 18px; }
        .control-row { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
        label { display: block; font-size: 0.93rem; margin-bottom: 8px; color: var(--muted); }
        input, select { width: 100%; border-radius: 14px; border: 1px solid rgba(148, 163, 184, 0.14); background: rgba(15, 23, 42, 0.88); color: var(--text); padding: 14px 16px; font-size: 0.95rem; }
        .big-button { width: 100%; border: none; border-radius: 16px; background: linear-gradient(135deg, #8b5cf6, #4338ca); color: white; font-size: 1rem; font-weight: 700; padding: 18px 22px; cursor: pointer; transition: transform .2s ease, filter .2s ease; }
        .big-button:hover { filter: brightness(1.05); transform: translateY(-1px); }
        .metric-row { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; color: var(--muted); font-size: 0.95rem; }
        .metric-row span { display: inline-flex; align-items: center; gap: 8px; }
        .metric-dot { width: 9px; height: 9px; border-radius: 999px; background: #65a30d; }
        .feed-box { background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(148, 163, 184, 0.1); border-radius: 22px; min-height: 240px; padding: 18px; overflow-y: auto; }
        .feed-item { display: flex; justify-content: space-between; gap: 18px; padding: 12px 0; border-bottom: 1px solid rgba(148, 163, 184, 0.08); }
        .feed-item:last-child { border-bottom: none; }
        .feed-item strong { color: white; }
        .feed-item span { color: var(--muted); }
        .status-available { color: var(--success); }
        .status-taken { color: var(--warning); }
        .status-error { color: var(--danger); }
        @media(max-width: 900px) { .hero-card { grid-template-columns: 1fr; } .mode-card { text-align: center; } .control-row { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="app-shell">
        <div class="page-header">
            <div>
                <h1>Roblox Username Checker</h1>
                <p>Fast dashboard-style username scanning with live feed and batch mode support.</p>
            </div>
            <div class="metric-row">
                <span><span class="metric-dot"></span>15 concurrent requests</span>
                <span><span class="metric-dot"></span>60 names per batch</span>
                <span><span class="metric-dot"></span>Roblox API validated</span>
            </div>
        </div>

        <div class="panel">
            <div class="section">
                <div class="modes-grid" id="modeGrid">
                    <div class="mode-card active" data-mode="4L" onclick="selectMode('4L')">
                        <span>4L</span>
                        <h3>4 Letter</h3>
                        <p>abcd</p>
                    </div>
                    <div class="mode-card" data-mode="4C" onclick="selectMode('4C')">
                        <span>4C</span>
                        <h3>4 Char</h3>
                        <p>a1b2</p>
                    </div>
                    <div class="mode-card" data-mode="5L" onclick="selectMode('5L')">
                        <span>5L</span>
                        <h3>5 Letter</h3>
                        <p>abcde</p>
                    </div>
                    <div class="mode-card" data-mode="5C" onclick="selectMode('5C')">
                        <span>5C</span>
                        <h3>5 Char</h3>
                        <p>ab1c2</p>
                    </div>
                    <div class="mode-card" data-mode="5N" onclick="selectMode('5N')">
                        <span>5N</span>
                        <h3>5 Number</h3>
                        <p>12345</p>
                    </div>
                    <div class="mode-card" data-mode="6L" onclick="selectMode('6L')">
                        <span>6L</span>
                        <h3>6 Letter</h3>
                        <p>abcdef</p>
                    </div>
                    <div class="mode-card" data-mode="6C" onclick="selectMode('6C')">
                        <span>6C</span>
                        <h3>6 Char</h3>
                        <p>ab1c2d</p>
                    </div>
                    <div class="mode-card" data-mode="6N" onclick="selectMode('6N')">
                        <span>6N</span>
                        <h3>6 Number</h3>
                        <p>123456</p>
                    </div>
                </div>
            </div>

            <div class="section hero-card">
                <div>
                    <div class="hero-stat">
                        <div class="stat-chip"><strong id="activeModeLabel">4L</strong><span>Selected mode</span></div>
                        <div class="stat-chip"><strong id="statusCount">0</strong><span>Checked</span></div>
                        <div class="stat-chip"><strong id="statusAvailable">0</strong><span>Available</span></div>
                    </div>
                    <div class="control-panel">
                        <div class="control-row">
                            <div>
                                <label for="scanCount">How many names</label>
                                <input id="scanCount" type="number" value="60" min="1" max="100" />
                            </div>
                            <div>
                                <label for="scanDelay">Request delay (ms)</label>
                                <input id="scanDelay" type="number" value="100" min="0" max="2000" />
                            </div>
                            <div>
                                <label for="batchSize">Batch size</label>
                                <input id="batchSize" type="number" value="60" min="1" max="100" disabled />
                            </div>
                        </div>
                        <button class="big-button" onclick="startScan()">Start Checking</button>
                        <div class="metric-row" style="margin-top: 10px; color: var(--muted);">
                            <span>Hit rate: <strong id="hitRate">0.00%</strong></span>
                        </div>
                    </div>
                </div>
                <div class="feed-box" id="liveFeed">
                    <strong>Live Feed</strong>
                    <div id="feedItems" style="margin-top: 12px; color: var(--muted);">Start checking to see results here.</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const modeConfig = {
            '4L': { length: 4, type: 'letters' },
            '4C': { length: 4, type: 'mixed' },
            '5L': { length: 5, type: 'letters' },
            '5C': { length: 5, type: 'mixed' },
            '5N': { length: 5, type: 'numbers' },
            '6L': { length: 6, type: 'letters' },
            '6C': { length: 6, type: 'mixed' },
            '6N': { length: 6, type: 'numbers' }
        };

        let selectedMode = '4L';
        let scanning = false;

        function selectMode(id) {
            selectedMode = id;
            document.getElementById('activeModeLabel').innerText = id;
            document.querySelectorAll('.mode-card').forEach(card => {
                card.classList.toggle('active', card.dataset.mode === id);
            });
            document.getElementById('feedItems').innerHTML = 'Start checking to see results here.';
            updateStatus(0, 0);
        }

        function updateStatus(checked, available) {
            document.getElementById('statusCount').innerText = checked;
            document.getElementById('statusAvailable').innerText = available;
            const rate = checked > 0 ? ((available / checked) * 100).toFixed(2) : '0.00';
            document.getElementById('hitRate').innerText = `${rate}%`;
        }

        async function postJson(url, data) {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            return response.json();
        }

        function pushFeed(message, status) {
            const feed = document.getElementById('feedItems');
            const item = document.createElement('div');
            item.className = 'feed-item';
            const text = document.createElement('strong');
            text.innerText = message;
            const badge = document.createElement('span');
            badge.innerText = status;
            badge.className = status === 'AVAILABLE' ? 'status-available' : status === 'TAKEN' ? 'status-taken' : 'status-error';
            item.appendChild(text);
            item.appendChild(badge);
            if (feed.innerHTML.includes('Start checking')) {
                feed.innerHTML = '';
            }
            feed.prepend(item);
            if (feed.childElementCount > 12) {
                feed.removeChild(feed.lastChild);
            }
        }

        async function startScan() {
            if (scanning) return;
            scanning = true;
            const count = Number(document.getElementById('scanCount').value) || 60;
            const delay = Number(document.getElementById('scanDelay').value) || 100;
            const config = modeConfig[selectedMode];
            if (!config) return;

            let checked = 0;
            let available = 0;
            updateStatus(checked, available);
            document.getElementById('feedItems').innerHTML = '';

            for (let i = 0; i < count; i++) {
                const result = await postJson('/api/check', {
                    mode: 'generate',
                    count: 1,
                    length: config.length,
                    username_type: config.type
                });

                const data = result.results ? result.results[0] : null;
                if (!data) {
                    pushFeed('Unexpected response', 'ERROR');
                } else {
                    const status = data.available ? 'AVAILABLE' : 'TAKEN';
                    if (data.available) available += 1;
                    checked += 1;
                    pushFeed(`${data.username}`, status);
                }
                updateStatus(checked, available);
                await new Promise(resolve => setTimeout(resolve, delay));
            }
            scanning = false;
        }

        selectMode(selectedMode);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

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
            if not isinstance(usernames, list):
                return jsonify(error='usernames must be a list'), 400
            results = checker.check_multiple([u.strip() for u in usernames if u.strip()])
            return jsonify(results=results)

        if mode == 'generate':
            count = int(payload.get('count', 10))
            length = int(payload.get('length', 6))
            username_type = payload.get('username_type', 'mixed')

            if count <= 0 or length < checker.USERNAME_MIN_LENGTH or length > checker.USERNAME_MAX_LENGTH:
                return jsonify(error='Invalid count or length'), 400

            if username_type not in {'letters', 'numbers', 'mixed'}:
                username_type = 'mixed'

            usernames = []
            while len(usernames) < count:
                username = checker.generate_random_username(length=length, username_type=username_type)
                if username not in usernames:
                    usernames.append(username)

            results = checker.check_multiple(usernames)
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
