import os
import datetime
from flask import Flask, request, render_template, jsonify
from groq import Groq

app = Flask(__name__)

# Configure Groq client
GROQ_API_KEY = os.environ.get("Voogle")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

GROQ_MODEL = "llama-3.3-70b-versatile"

# Initialize database on startup
from database import init_db, save_query, get_all_queries
with app.app_context():
    init_db()


def get_ai_response(message: str) -> str:
    """Send a message to Groq and return the text response."""
    if not client:
        return "Error: Groq API key is not configured."
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": message}],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error contacting Groq: {str(e)}"


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

    # Get AI response
    ai_response = get_ai_response(message_text)

    # Save to database
    timestamp = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
    save_query(
        phone_number=sender,
        user_query=message_text,
        gemini_response=ai_response,
        timestamp=timestamp,
    )

    # Africa's Talking expects plain text back
    return ai_response, 200, {"Content-Type": "text/plain"}


@app.route("/admin")
def admin_dashboard():
    """Admin dashboard showing all SMS queries and AI responses."""
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
    key_exists = GROQ_API_KEY is not None
    key_preview = (GROQ_API_KEY[:6] + "...") if key_exists else None
    return jsonify({
        "groq_api_key_exists": key_exists,
        "groq_api_key_preview": key_preview,
        "model": GROQ_MODEL,
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
