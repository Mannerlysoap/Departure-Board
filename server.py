import os
import sys
import time
import requests
import traceback
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# --- 1. LOAD CONFIGURATION ---
# Load .env file from the current directory
load_dotenv()

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)

# Configuration
PORT = int(os.getenv("PORT", 3000))
STOP_ID = os.getenv("STOP_ID", "U837Z1P")
API_KEY = os.getenv("GOLEMIO_API_KEY")
GOLEMIO_URL = "https://api.golemio.cz/v2/pid/departureboards"

# --- 2. STARTUP 
print("DEBUG STARTUP ")
print(f"STOP_ID: {STOP_ID}")
if API_KEY:
    print(f"🔑 API_KEY: Loaded ({len(API_KEY)} characters)")
else:
    print("❌ API_KEY: MISSING or EMPTY! Check your .env file.")
print("---------------------")

# In-Memory Cache
cache = {"data": None, "last_fetch": 0}

def transform_data(api_response):
    """
    Safely transforms Golemio API data for the frontend.
    """
    cleaned_data = []
    
    # Normalize input to a list
    raw_list = []
    if isinstance(api_response, list):
        raw_list = api_response
    elif isinstance(api_response, dict):
        raw_list = api_response.get("departures", [])
    
    for dep in raw_list:
        try:
            # Safe extraction with defaults
            route = dep.get("route", {}) or {}
            trip = dep.get("trip", {}) or {}
            timestamps = dep.get("departure_timestamp", {}) or {}

            # Time Logic
            predicted = timestamps.get("predicted")
            scheduled = timestamps.get("scheduled")
            # If both are None, use current time to prevent crash
            final_time = predicted if predicted else (scheduled if scheduled else datetime.now().isoformat())

            cleaned_data.append({
                "line": route.get("short_name", "?"),
                "destination": trip.get("headsign", "Unknown"),
                "departureTime": final_time,
                "isDelay": (dep.get("delay_minutes", 0) > 0)
            })
        except Exception:
            # If one row fails, skip it but don't crash the server
            continue

    return cleaned_data

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/departures')
def get_departures():
    global cache
    now = time.time()

    # Serve Cache
    if cache["data"] and (now - cache["last_fetch"] < 60):
        print(f"[CACHE] Serving {len(cache['data'])} items")
        return jsonify(cache["data"])

    print("[FETCH] Requesting data from Golemio...")

    try:
        if not API_KEY:
            raise ValueError("API Key is missing. Check server logs.")

        headers = {
            "X-Access-Token": API_KEY,
            "Content-Type": "application/json"
        }
        params = {
            "ids": STOP_ID,
            "minutesAfter": 60,
            "limit": 12,
            "mode": "departures"
        }

        response = requests.get(GOLEMIO_URL, headers=headers, params=params, timeout=10)
        
        # If API returns 401/404/500, this raises an error
        response.raise_for_status()

        # Transform
        data = transform_data(response.json())
        
        # Update Cache
        cache["data"] = data
        cache["last_fetch"] = now
        
        print(f"[SUCCESS] Fetched {len(data)} items")
        return jsonify(data)

    except Exception as e:
        # --- DEBUG MODE: SEND ERROR TO BROWSER ---
        error_msg = f"{type(e).__name__}: {str(e)}"
        print(f"❌ ERROR: {error_msg}")
        traceback.print_exc()
        
        # Return the actual error details to the frontend
        return jsonify({
            "error": "Backend Error",
            "details": error_msg,
            "tip": "Check docker logs for full stack trace"
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
