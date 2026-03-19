import os
import time
import json
import requests
import threading
import logging
from functools import wraps
from datetime import datetime
from flask import Flask, jsonify, request, render_template, Response, make_response, send_from_directory
from werkzeug.utils import secure_filename
from flask_cors import CORS
from dotenv import load_dotenv

# --- 1. CONFIGURATION ---
load_dotenv()

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

CONFIG_FILE = 'config.json'
# Use absolute path for upload folder to be safe
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'public', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

PORT_PUBLIC = int(os.getenv("PORT", 3000))
PORT_ADMIN = 7171

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

CIS_ID = os.getenv("TARGET_NODE_CISID") or os.getenv("CIS_ID", "1262")
API_KEY = os.getenv("GOLEMIO_API_KEY")
DIR2_ENDSTATION = os.getenv("DIR2_ENDSTATION", "")
GOLEMIO_URL = "https://api.golemio.cz/v2/pid/departureboards"

# Admin Credentials
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "secret123")

# --- 2. CONFIG HELPERS ---
def load_config():
    config = {
        "header_title": "HMM...KDY?",
        "dir0_label": "Do centra",
        "dir1_label": "Na spojku",
        "status_bar": "System Online",
        "image_filename": "",
        "image_overlay_text": ""
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                loaded = json.load(f)
                config.update(loaded)
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    
    # Ensure all keys exist
    if "image_filename" not in config:
        config["image_filename"] = ""
    if "image_overlay_text" not in config:
        config["image_overlay_text"] = ""
    return config

def save_config(data):
    # Load current config to merge
    current = load_config()
    current.update(data)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(current, f, indent=2)
    logger.info(f"[ADMIN] Configuration updated and saved to {CONFIG_FILE}")

# --- 3. BASIC AUTH DECORATOR ---
def check_auth(username, password):
    return username == ADMIN_USER and password == ADMIN_PASS

def authenticate():
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# --- 4. SHARED LOGIC ---
cache = {"data": None, "last_fetch": 0}

def transform_data(api_response):
    raw_list = api_response.get("departures", []) if isinstance(api_response, dict) else api_response
    grouped_data = {"direction0": [], "direction1": []}
    
    for dep in raw_list:
        try:
            route = dep.get("route", {}) or {}
            trip = dep.get("trip", {}) or {}
            timestamps = dep.get("departure_timestamp", {}) or {}
            delay = dep.get("delay", {}) or {}

            predicted = timestamps.get("predicted")
            scheduled = timestamps.get("scheduled")
            final_time = predicted if predicted else (scheduled if scheduled else "")
            if not final_time: continue

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
            
            is_dir2 = False
            if DIR2_ENDSTATION and DIR2_ENDSTATION.lower() in destination.lower():
                is_dir2 = True
            else:
                is_dir2 = (trip.get("direction_id", dep.get("direction_id", 0)) == 1)

            key = "direction1" if is_dir2 else "direction0"
            grouped_data[key].append(departure_item)
        except Exception as e:
            logger.error(f"Error processing departure: {e}")
            continue
    return grouped_data

# --- 5. PUBLIC APP (Port 3000) ---
public_app = Flask(__name__, static_folder='public', static_url_path='')
CORS(public_app)

@public_app.route('/')
def index():
    logger.info(f"[PUBLIC] GET / - {request.remote_addr}")
    return public_app.send_static_file('index.html')

@public_app.route('/api/config')
def get_public_config():
    logger.info(f"[PUBLIC] GET /api/config - {request.remote_addr}")
    config = load_config()
    response = make_response(jsonify(config))
    # Ensure no caching
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@public_app.route('/api/departures')
def get_departures():
    global cache
    now = time.time()
    logger.info(f"[PUBLIC] GET /api/departures - {request.remote_addr}")
    
    if cache["data"] and (now - cache["last_fetch"] < 30):
        return jsonify(cache["data"])

    try:
        if not API_KEY:
            return jsonify({"error": "Configuration Error", "details": "API Key missing"}), 500
        headers = {"X-Access-Token": API_KEY, "Content-Type": "application/json"}
        params = {"cisIds": CIS_ID, "minutesAfter": 60, "limit": 30, "mode": "departures"}
        response = requests.get(GOLEMIO_URL, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            return jsonify({"error": f"Golemio API Error {response.status_code}", "details": response.text}), response.status_code
        data = transform_data(response.json())
        cache["data"] = data
        cache["last_fetch"] = now
        return jsonify(data)
    except Exception as e:
        logger.error(f"[PUBLIC] Error fetching departures: {e}")
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500

@public_app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    # Use explicit serving for uploads
    return send_from_directory(UPLOAD_FOLDER, filename)

# --- 6. ADMIN APP (Port 7171) ---
admin_app = Flask(__name__, template_folder='templates')

@admin_app.route('/')
@requires_auth
def admin_index():
    logger.info(f"[ADMIN] GET / - {request.remote_addr}")
    config = load_config()
    return render_template('admin.html', config=config)

@admin_app.route('/api/config', methods=['POST'])
@requires_auth
def update_config():
    logger.info(f"[ADMIN] POST /api/config - {request.remote_addr}")
    new_config = request.json
    save_config(new_config)
    return jsonify({"status": "success"})

@admin_app.route('/api/upload', methods=['POST'])
@requires_auth
def upload_file():
    logger.info(f"[ADMIN] POST /api/upload - {request.remote_addr}")
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Ensure we save with absolute path
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        logger.info(f"File saved to: {file_path}")
        
        # Update config with filename
        config = load_config()
        config['image_filename'] = filename
        save_config(config)
        
        return jsonify({"status": "success", "filename": filename})
    return jsonify({"error": "File type not allowed"}), 400

# --- 7. RUNNERS ---
def run_public():
    logger.info(f"Starting Public Server on port {PORT_PUBLIC}...")
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    public_app.run(host='0.0.0.0', port=PORT_PUBLIC, debug=False, use_reloader=False)

def run_admin():
    logger.info(f"Starting Admin Server on port {PORT_ADMIN}...")
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    admin_app.run(host='0.0.0.0', port=PORT_ADMIN, debug=False, use_reloader=False)

if __name__ == '__main__':
    t1 = threading.Thread(target=run_public)
    t2 = threading.Thread(target=run_admin)
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
