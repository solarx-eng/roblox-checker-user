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
        body { font-family: Arial, sans-serif; background: #111827; color: #f8fafc; margin: 0; padding: 0; }
        .container { max-width: 980px; margin: 24px auto; padding: 20px; }
        h1 { margin-bottom: 10px; font-size: 2.2rem; }
        .card { background: #1f2937; border: 1px solid #374151; border-radius: 14px; padding: 20px; margin-bottom: 20px; }
        label { display: block; margin-bottom: 6px; font-weight: 600; }
        input, textarea, select { width: 100%; padding: 10px 12px; border: 1px solid #4b5563; border-radius: 8px; background: #111827; color: #f8fafc; }
        button { background: #2563eb; border: none; color: white; padding: 12px 18px; border-radius: 10px; cursor: pointer; transition: background .2s ease; }
        button:hover { background: #1d4ed8; }
        .row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .row.single { grid-template-columns: 1fr; }
        .result { margin-top: 14px; font-size: 0.95rem; white-space: pre-wrap; }
        .status-good { color: #22c55e; }
        .status-bad { color: #f97316; }
        .status-error { color: #f87171; }
        .footer { text-align: center; margin-top: 20px; color: #9ca3af; }
        @media(max-width: 760px) { .row { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <h1>Roblox Username Checker</h1>
        <p>Use the web app to check usernames with the Roblox API from your browser.</p>

        <div class="card">
            <h2>Check one username</h2>
            <label for="singleUsername">Username</label>
            <input id="singleUsername" placeholder="Enter username" />
            <button onclick="checkSingle()">Check Username</button>
            <div id="singleResult" class="result"></div>
        </div>

        <div class="card">
            <h2>Check multiple usernames</h2>
            <label for="multipleUsernames">Usernames (comma-separated)</label>
            <textarea id="multipleUsernames" rows="5" placeholder="one,two,three"></textarea>
            <button onclick="checkMultiple()">Check Multiple</button>
            <div id="multipleResult" class="result"></div>
        </div>

        <div class="card">
            <h2>Generate and check random usernames</h2>
            <div class="row single">
                <div>
                    <label for="generateCount">Count</label>
                    <input id="generateCount" type="number" value="10" min="1" max="100" />
                </div>
                <div>
                    <label for="generateLength">Length</label>
                    <input id="generateLength" type="number" value="6" min="3" max="20" />
                </div>
                <div>
                    <label for="generateType">Type</label>
                    <select id="generateType">
                        <option value="letters">Letters only</option>
                        <option value="mixed">Letters + numbers</option>
                    </select>
                </div>
            </div>
            <button onclick="generateAndCheck()">Generate &amp; Check</button>
            <div id="generateResult" class="result"></div>
        </div>

        <div class="footer">
            <p>Run this app by starting the Python server and opening <strong>http://127.0.0.1:5000</strong>.</p>
        </div>
    </div>

    <script>
        async function postJson(url, data) {
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            return response.json();
        }

        function formatResult(result) {
            if (result.available === true) return `✅ ${result.username}: AVAILABLE`;
            if (result.available === false) return `✖ ${result.username}: TAKEN`;
            return `❌ ${result.username}: ERROR (${result.error || 'unknown'})`;
        }

        async function checkSingle() {
            const username = document.getElementById('singleUsername').value.trim();
            if (!username) { document.getElementById('singleResult').innerText = 'Please enter a username.'; return; }
            document.getElementById('singleResult').innerText = 'Checking...';
            const data = await postJson('/api/check', { mode: 'single', username });
            document.getElementById('singleResult').innerText = formatResult(data.result || data);
        }

        async function checkMultiple() {
            const raw = document.getElementById('multipleUsernames').value.trim();
            if (!raw) { document.getElementById('multipleResult').innerText = 'Please enter usernames.'; return; }
            const usernames = raw.split(',').map(u => u.trim()).filter(Boolean);
            document.getElementById('multipleResult').innerText = 'Checking...';
            const data = await postJson('/api/check', { mode: 'multiple', usernames });
            if (data.error) {
                document.getElementById('multipleResult').innerText = data.error;
                return;
            }
            document.getElementById('multipleResult').innerText = data.results.map(formatResult).join('\n');
        }

        async function generateAndCheck() {
            const count = Number(document.getElementById('generateCount').value);
            const length = Number(document.getElementById('generateLength').value);
            const type = document.getElementById('generateType').value;
            if (!count || !length) { document.getElementById('generateResult').innerText = 'Please enter count and length.'; return; }
            document.getElementById('generateResult').innerText = 'Generating and checking...';
            const data = await postJson('/api/check', {
                mode: 'generate',
                count,
                length,
                letters_only: type === 'letters'
            });
            if (data.error) {
                document.getElementById('generateResult').innerText = data.error;
                return;
            }
            document.getElementById('generateResult').innerText = data.results.map(formatResult).join('\n');
        }
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
            letters_only = bool(payload.get('letters_only', False))

            if count <= 0 or length < checker.USERNAME_MIN_LENGTH or length > checker.USERNAME_MAX_LENGTH:
                return jsonify(error='Invalid count or length'), 400

            usernames = []
            while len(usernames) < count:
                username = checker.generate_random_username(length=length, letters_only=letters_only)
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
