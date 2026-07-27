import os
import datetime
from flask import Flask, request, render_template, jsonify
import google.generativeai as genai
from database import init_db, save_query, get_all_queries

app = Flask(__name__)

# Configure Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Initialize database on startup
with app.app_context():
    init_db()


def get_gemini_response(message: str) -> str:
    """Send a message to Gemini and return the text response."""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(message)
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
