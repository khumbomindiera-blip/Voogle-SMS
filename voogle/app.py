import os
import datetime
from flask import Flask, request, render_template, jsonify
from google import genai

app = Flask(__name__)

# Configure Gemini client
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

# Initialize database on startup
from database import init_db, save_query, get_all_queries
with app.app_context():
    init_db()


def get_gemini_response(message: str) -> str:
    """Send a message to Gemini and return the text response."""
    if not client:
        return "Error: GEMINI_API_KEY is not configured."
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=message,
        )
        return response.text.strip()
    except Exception as e:
        return f"Error contacting Gemini: {str(e)}"


@app.route("/sms", methods=["POST"])
def receive_sms():
    """
    Africa's Talking SMS webhook endpoint.
    Receives POST data with fields: from, to, text, date, id, linkId.
    Returns plain text response that AT will deliver back as SMS.
    """
    sender = request.form.get("from", "").strip()
    message_text = request.form.get("text", "").strip()

    if not sender or not message_text:
        return "Missing sender or message.", 400

    # Get Gemini response
    gemini_response = get_gemini_response(message_text)

    # Save to database
    timestamp = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
    save_query(
        phone_number=sender,
        user_query=message_text,
        gemini_response=gemini_response,
        timestamp=timestamp,
    )

    # Africa's Talking expects plain text back
    return gemini_response, 200, {"Content-Type": "text/plain"}


@app.route("/admin")
def admin_dashboard():
    """Admin dashboard showing all SMS queries and Gemini responses."""
    queries = get_all_queries()
    return render_template("dashboard.html", queries=queries)


@app.route("/admin/api/queries")
def api_queries():
    """JSON endpoint for dashboard data."""
    queries = get_all_queries()
    return jsonify(queries)


@app.route("/debug")
def debug():
    """Temporary debug endpoint — shows key presence and model config, never the full key."""
    key_exists = GEMINI_API_KEY is not None
    key_preview = (GEMINI_API_KEY[:6] + "...") if key_exists else None
    return jsonify({
        "gemini_api_key_exists": key_exists,
        "gemini_api_key_preview": key_preview,
        "model": "gemini-2.5-flash",
    })


@app.route("/health")
def health():
    return {"status": "ok", "app": "Voogle"}, 200


@app.route("/")
def index():
    return (
        "<h2>Voogle is running.</h2>"
        "<p>Webhook endpoint: <code>POST /sms</code></p>"
        "<p><a href='/admin'>Admin Dashboard</a></p>"
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
