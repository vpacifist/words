from flask import Flask, jsonify

app = Flask(__name__)

WORDS = [
    {"de": "Haus", "ru": "дом"},
    {"de": "Baum", "ru": "дерево"},
    {"de": "Wasser", "ru": "вода"},
]

@app.route("/")
def home():
    return "Hello from Railway + Flask!"

@app.route("/api/words")
def get_words():
    return jsonify(WORDS)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
