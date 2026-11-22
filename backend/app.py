import os
from flask import Flask, jsonify
from flask_cors import CORS
from config import PORT
from auth_manager import load_session, perform_login, load_account_pool
from routes import batches_bp, video_bp, proxy_bp

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Register Modular Blueprints
app.register_blueprint(batches_bp)
app.register_blueprint(video_bp)
app.register_blueprint(proxy_bp)

# Health & System Status Endpoints
@app.route("/", methods=["GET"])
@app.route("/health", methods=["GET"])
@app.route("/api/health", methods=["GET"])
def health():
    pool = load_account_pool()
    return jsonify({
        "status": 200,
        "message": "Disha Pro Modular Backend Running",
        "active_accounts_in_pool": len(pool),
        "service": "Online"
    })

@app.route("/api/user", methods=["GET"])
def api_user():
    session = load_session()
    if not session:
        session = perform_login()
    if session:
        return jsonify({
            "status": 200,
            "data": {
                "name": session.get("name", "Disha Pro Student"),
                "phone": session.get("phone", "9876543210"),
                "email": session.get("email", "student@disha.online"),
                "is_paid_user": "1"
            }
        })
    return jsonify({"status": 401, "message": "No active session"}), 401

if __name__ == "__main__":
    print(f"[*] Starting Disha Pro Modular Backend on port {PORT}...")
    load_account_pool()
    app.run(host="0.0.0.0", port=PORT, debug=False)
