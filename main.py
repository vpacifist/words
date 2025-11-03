from flask import Flask, jsonify, send_from_directory, request
import json, os
from datetime import datetime, timedelta
import re
from db import init_db, get_words, add_word, update_result, reset_user

DATA_FILE = "data.json"
DATA_FILE_PREFIX = "data"
INTERVALS = [0, 10/60, 1, 12, 24, 72, 168, 336, 720, 2160, 4320, 8760, 17520]

app = Flask(__name__, static_folder="public")

@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/words")
def get_words_api():
    uid = request.args.get("user_id", "public")
    return jsonify(get_words(uid))

@app.route("/api/add_word", methods=["POST"])
def add_word_api():
    uid = request.args.get("user_id", "public")
    body = request.get_json()
    w = add_word(uid, body["de"], body["ru"])
    return jsonify({"status": "ok", "added": w})

@app.route("/api/result", methods=["POST"])
def save_result_api():
    uid = request.args.get("user_id", "public")
    data = request.get_json()
    w = update_result(uid, data["id"], data["correct"], data["reverse"], INTERVALS, fast=(request.args.get("fast")=="1"))
    if not w:
        return jsonify({"status": "error", "message": "word not found"}), 404
    return jsonify({"status": "ok", "updated": w})

@app.route("/api/reset", methods=["POST"])
def reset_stats_api():
    uid = request.args.get("user_id", "public")
    reset_user(uid)
    return jsonify({"status": "ok"})

@app.route("/api/intervals")
def get_intervals():
    return jsonify(INTERVALS)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8080)
