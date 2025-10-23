from flask import Flask, jsonify, send_from_directory, request
import json, os
from datetime import datetime

DATA_FILE = "data.json"

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
