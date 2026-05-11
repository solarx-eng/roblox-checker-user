# Roblox Username Checker Web

This project includes a Flask web app to check Roblox username availability using Roblox API endpoints.

## Files

- `roblox_username_checker.py` — existing checker logic
- `roblox_username_checker_web.py` — Flask web app wrapper
- `requirements.txt` — Python package dependencies
- `Procfile` — deployment command for Render/Heroku-style hosts
- `runtime.txt` — Python runtime version

## Run locally

1. Open PowerShell
2. Navigate to the folder:
   ```powershell
   cd C:\Users\solar\Downloads
   ```
3. Install dependencies:
   ```powershell
   python -m pip install -r requirements.txt
   ```
4. Start the web app:
   ```powershell
   python roblox_username_checker_web.py
   ```
5. Open this URL in your browser:
   ```text
   http://127.0.0.1:5000
   ```

## Deploy to Render

1. Create a free account at https://render.com
2. Create a new **Web Service**
3. Connect your GitHub repo or upload these files to a repo
4. Set the build command to:
   ```bash
   pip install -r requirements.txt
   ```
5. Set the start command to:
   ```bash
   gunicorn roblox_username_checker_web:app
   ```
6. Deploy and open the public URL Render gives you.

## Deploy to Replit

1. Create a new Python Repl
2. Upload all project files
3. In `Packages`, install `Flask`, `requests`, and `gunicorn`
4. Set the run command to:
   ```bash
   gunicorn roblox_username_checker_web:app
   ```
5. Run the Repl and open the web link.

## Notes

- This app is local by default, but deployment files are included for public hosting.
- The website uses the Roblox API through the backend; the browser UI only sends requests to your server.
