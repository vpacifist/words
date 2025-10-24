from flask import Flask, jsonify, send_from_directory, request
import json, os
from datetime import datetime, timedelta

DATA_FILE = "data.json"
INTERVALS = [0, 10/60, 1, 12, 24, 72, 168, 336, 720, 2160, 4320, 8760, 17520]

def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

app = Flask(__name__, static_folder="public")

@app.route("/")
def home():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/words")
def get_words():
    return jsonify(load_data())

@app.route("/api/add_word", methods=["POST"])
def add_word():
    data = load_data()
    new_word = request.get_json()

    new_word["id"] = len(data) + 1
    new_word["next_de_ru"] = datetime.now().isoformat()
    new_word["next_ru_de"] = datetime.now().isoformat()
    new_word["interval_de_ru"] = 0
    new_word["interval_ru_de"] = 0
    new_word["correct_de_ru"] = 0
    new_word["correct_ru_de"] = 0
    new_word["created_at"] = datetime.now().isoformat()
    new_word["history"] = []

    data.append(new_word)
    save_data(data)
    return jsonify({"status": "ok", "added": new_word})

@app.route("/api/result", methods=["POST"])
def save_result():
    data = load_data()
    result = request.get_json()
    word_id = result["id"]
    correct = result["correct"]
    reverse = result["reverse"]

    for w in data:
        if w["id"] == word_id:
            w.setdefault("history", []).append({
                "date": datetime.now().date().isoformat(),
                "correct": correct,
                "reverse": reverse
            })
            key = "correct_ru_de" if reverse else "correct_de_ru"
            w[key] += 1 if correct else 0

            key_int = "interval_ru_de" if reverse else "interval_de_ru"
            key_next = "next_ru_de" if reverse else "next_de_ru"

            if correct:
                current = w[key_int]
                w[key_int] = min(current + 1, len(INTERVALS) - 1)
            else:
                w[key_int] = 0

            hours = INTERVALS[w[key_int]]
            if request.args.get("fast") == "1":
                hours = hours / 30 if hours else 0
            w[key_next] = (datetime.now() + timedelta(hours=hours)).isoformat()

            save_data(data)
            return jsonify({"status": "ok", "updated": w})

    return jsonify({"status": "error", "message": "word not found"}), 404

@app.route("/api/reset", methods=["POST"])
def reset_stats():
    data = load_data()
    for w in data:
        w["interval_de_ru"] = 0
        w["interval_ru_de"] = 0
        w["correct_de_ru"] = 0
        w["correct_ru_de"] = 0
        w["next_de_ru"] = datetime.now().isoformat()
        w["next_ru_de"] = datetime.now().isoformat()
    save_data(data)
    return jsonify({"status": "ok"})

@app.route("/api/intervals")
def get_intervals():
    return jsonify(INTERVALS)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
