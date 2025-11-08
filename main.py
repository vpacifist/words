import eventlet
eventlet.monkey_patch()
from flask import Flask, jsonify, send_from_directory, request, session
from flask_socketio import SocketIO, emit
from db import init_db, get_words, add_word, update_result, reset_user, create_user, verify_user
import os
import jwt
from datetime import datetime, timedelta, timezone


INTERVALS = [0, 10/60, 1, 12, 24, 72, 168, 336, 720, 2160, 4320, 8760, 17520]

app = Flask(__name__, static_folder="public")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-jwt-key")
JWT_EXPIRE_HOURS = 72

@socketio.on("client_state")
def handle_client_state(data):
    required = {"mode", "timestamp", "version"}
    if not all(k in data for k in required):
        return
    emit("state_sync", {"type": "client", "state": data}, broadcast=True)

@socketio.on("request_full_state")
def handle_request_full_state():
    uid = session.get("user_id")
    if uid:
        data = get_user_state(uid)
        # только данные, без ui-состояния
        emit("state_sync", {"type": "data", "state": data})

def get_user_state(uid):
    from db import get_words
    return {
        "words": get_words(uid),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def emit_state(uid):
    state = get_user_state(uid)
    socketio.emit("state_sync", {"type": "server", "state": state})

@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    ok = create_user(data["email"], data["password"])
    return jsonify({"status": "ok" if ok else "error", "message": "created" if ok else "exists"})

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    if verify_user(data["email"], data["password"]):
        session["user_id"] = data["email"]
        token = jwt.encode(
            {"email": data["email"], "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)},
            JWT_SECRET, algorithm="HS256")
        return jsonify({"status": "ok", "user": data["email"], "token": token})
    return jsonify({"status": "error", "message": "invalid credentials"}), 401

@app.route("/api/refresh_token", methods=["POST"])
def refresh_token():
    data = request.get_json()
    token = data.get("token")
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        new_token = jwt.encode(
            {"email": decoded["email"], "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)},
            JWT_SECRET, algorithm="HS256")
        session["user_id"] = decoded["email"]
        return jsonify({"status": "ok", "token": new_token})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 401

@app.route("/api/words")
def get_words_api():
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return jsonify({"error": "missing token"}), 401
    try:
        token = auth.split(" ")[1]
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        uid = decoded["email"]
    except Exception:
        return jsonify({"error": "invalid token"}), 401
    return jsonify(get_words(uid))

@app.route("/api/add_word", methods=["POST"])
def add_word_api():
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return jsonify({"error": "missing token"}), 401
    try:
        token = auth.split(" ")[1]
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        uid = decoded["email"]
    except Exception:
        return jsonify({"error": "invalid token"}), 401
    body = request.get_json()
    w = add_word(uid, body["de"], body["ru"])
    emit_state(uid)
    return jsonify({"status": "ok", "added": w})

@app.route("/api/result", methods=["POST"])
def save_result_api():
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return jsonify({"error": "missing token"}), 401
    try:
        token = auth.split(" ")[1]
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        uid = decoded["email"]
    except Exception:
        return jsonify({"error": "invalid token"}), 401
    data = request.get_json()
    w = update_result(uid, data["id"], data["correct"], data["reverse"], INTERVALS, fast=(request.args.get("fast")=="1"))
    if not w:
        return jsonify({"status": "error", "message": "word not found"}), 404
    emit_state(uid)
    return jsonify({"status": "ok", "updated": w})

@app.route("/api/reset", methods=["POST"])
def reset_stats_api():
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return jsonify({"error": "missing token"}), 401
    try:
        token = auth.split(" ")[1]
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        uid = decoded["email"]
    except Exception:
        return jsonify({"error": "invalid token"}), 401
    reset_user(uid)
    emit_state(uid)
    return jsonify({"status": "ok"})

@app.route("/api/intervals")
def get_intervals():
    return jsonify(INTERVALS)

@app.route("/api/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    return jsonify({"status": "ok", "message": "logged out"})

if __name__ == "__main__":
    init_db()
    socketio.run(app, host="0.0.0.0", port=8080, debug=False, allow_unsafe_werkzeug=True)
