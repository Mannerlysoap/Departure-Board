import os
import time
import requests
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# --- 1. CONFIGURATION ---
load_dotenv()

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)

PORT = int(os.getenv("PORT", 3000))
# Default to a placeholder if not provided. 
# 1262 is the cisId for "Průběžná" in Prague.
CIS_ID = os.getenv("TARGET_NODE_CISID") or os.getenv("CIS_ID", "1262")
API_KEY = os.getenv("GOLEMIO_API_KEY")

# New configuration for filtering Direction 2
DIR2_ENDSTATION = os.getenv("DIR2_ENDSTATION", "")

GOLEMIO_URL = "https://api.golemio.cz/v2/pid/departureboards"

# In-Memory Cache
cache = {"data": None, "last_fetch": 0}

def transform_data(api_response):
    """
    Transforms Golemio V2 response into a unified format grouped by direction.
    """
    raw_list = api_response.get("departures", []) if isinstance(api_response, dict) else api_response
    
    grouped_data = {
        "direction0": [], # Direction 1 column
        "direction1": []  # Direction 2 column
    }
    
    for dep in raw_list:
        try:
            route = dep.get("route", {}) or {}
            trip = dep.get("trip", {}) or {}
            timestamps = dep.get("departure_timestamp", {}) or {}
            delay = dep.get("delay", {}) or {}

            # Time calculation
            predicted = timestamps.get("predicted")
            scheduled = timestamps.get("scheduled")
            final_time = predicted if predicted else (scheduled if scheduled else "")
            
            if not final_time:
                continue

            # Delay
            delay_min = delay.get("minutes", dep.get("delay_minutes", 0))
            destination = trip.get("headsign", dep.get("headsign", "Unknown"))
            
            departure_item = {
                "line": route.get("short_name", dep.get("line", "?")),
                "destination": destination,
                "departureTime": final_time,
                "isDelay": (delay_min > 0) if delay_min is not None else False,
                "delay": delay_min,
                "platform": dep.get("platform", "")
            }
            
            # Map to direction
            # If DIR2_ENDSTATION is defined, we check if destination matches.
            # Otherwise, we use direction_id from API.
            is_dir2 = False
            if DIR2_ENDSTATION and DIR2_ENDSTATION.lower() in destination.lower():
                is_dir2 = True
            else:
                # Fallback to API direction_id (1 is usually the "other" way)
                is_dir2 = (trip.get("direction_id", dep.get("direction_id", 0)) == 1)

            key = "direction1" if is_dir2 else "direction0"
            grouped_data[key].append(departure_item)
            
        except Exception as e:
            print(f"Error processing departure: {e}")
            continue

    return grouped_data

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/departures')
def get_departures():
    global cache
    now = time.time()

    # Serve from cache if within TTL (30s)
    if cache["data"] and (now - cache["last_fetch"] < 30):
        return jsonify(cache["data"])

    try:
        if not API_KEY:
            return jsonify({"error": "Configuration Error", "details": "API Key missing"}), 500

        headers = {
            "X-Access-Token": API_KEY,
            "Content-Type": "application/json"
        }
        
        # Use cisIds for station-wide aggregation
        params = {
            "cisIds": CIS_ID,
            "minutesAfter": 60,
            "limit": 30, # Increased limit to ensure we get both directions
            "mode": "departures"
        }

        print(f"[FETCH] Requesting departures for cisId: {CIS_ID}")
        response = requests.get(GOLEMIO_URL, headers=headers, params=params, timeout=10)
        
        if response.status_code != 200:
            return jsonify({"error": f"Golemio API Error {response.status_code}", "details": response.text}), response.status_code
            
        data = transform_data(response.json())
        cache["data"] = data
        cache["last_fetch"] = now
        
        return jsonify(data)

    except Exception as e:
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

if __name__ == '__main__':
    print(f"Starting server on port {PORT}...")
    print(f"Monitoring CIS ID: {CIS_ID}")
    print(f"Filtering Direction 2 by: {DIR2_ENDSTATION}")
    app.run(host='0.0.0.0', port=PORT)
