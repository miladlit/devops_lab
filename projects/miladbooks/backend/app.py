from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/books")
def books():
    return jsonify([
        {"title": "Docker Deep Dive", "author": "Nigel Poulton"},
        {"title": "Kubernetes Up & Running", "author": "Hightower"}
    ])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
