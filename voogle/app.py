import os
import logging
import datetime
from flask import Flask, request, render_template, jsonify
import google.generativeai as genai
from duckduckgo_search import DDGS
import africastalking

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── Flask ─────────────────────────────────────────────────────────────────────
app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-3.7-flash")
else:
    model = None

# ── Africa's Talking ──────────────────────────────────────────────────────────
AT_USERNAME = os.environ.get("AT_USERNAME", "sandbox")
AT_API_KEY = os.environ.get("AT_API_KEY")
AT_SENDER_ID = os.environ.get("AT_SENDER_ID", "")

if AT_API_KEY:
    africastalking.initialize(AT_USERNAME, AT_API_KEY)
    at_sms = africastalking.SMS

    log.info(
        "AT initialised — username=%s sender_id=%s api_key_set=%s",
        AT_USERNAME,
        AT_SENDER_ID,
        True
    )
else:
    at_sms = None
    log.warning("Africa's Talking API key not configured")

# ── Database ──────────────────────────────────────────────────────────────────
from database import init_db, save_query, get_all_queries
with app.app_context():
    init_db()

# ── Current-events detection ──────────────────────────────────────────────────
CURRENT_EVENT_KEYWORDS = [
    "news", "today", "latest", "current", "recent", "now", "tonight",
    "this week", "this month", "weather", "trending", "happening",
    "update", "score", "results", "election", "match", "game",
    "breaking", "died", "arrested", "launched", "announced", "released",
    "yesterday", "last night", "this morning",
]


def is_current_events_query(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in CURRENT_EVENT_KEYWORDS)


def search_web(query: str, max_results: int = 4) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return ""
        return "\n".join(
            f"- {r.get('title','')}: {r.get('body','')}" for r in results
        )
    except Exception as e:
        log.warning("Web search failed: %s", e)
        return ""

def get_ai_response(message: str):

    if not model:
        return "Error: Gemini API key not configured."

    try:

        context = ""

        if is_current_events_query(message):
            context = search_web(message)

        prompt = f"""
You are Voogle, an AI assistant for Malawi.

Rules:
- Reply in plain SMS format.
- Maximum 4 short sentences.
- Be practical and helpful.
- If climate, weather, farming or environment related, prioritize actionable advice.
- Use search results when available.
- If uncertain, say so.

Search Results:
{context}

Question:
{message}
"""

        response = model.generate_content(prompt)

        return response.text.strip()

    except Exception as e:
        return f"Error: {str(e)}"


def send_sms(recipient: str, message: str) -> dict:
    """
    Send an SMS via Africa's Talking and return a result dict.
    """

    if at_sms is None:
        return {
            "success": False,
            "status": "disabled",
            "error": "Africa's Talking not configured"
        }

    payload = {
        "to": recipient,
        "message": message,
        "sender_id": AT_SENDER_ID or None,
    }

    log.info("AT SMS request payload: %s", payload)

    try:
        response = at_sms.send(
            message=message,
            recipients=[recipient],
            **({"sender_id": AT_SENDER_ID} if AT_SENDER_ID else {})
        )

        log.info("AT SMS API response: %s", response)

        recipients_data = response.get(
            "SMSMessageData", {}
        ).get("Recipients", [])

        if recipients_data:
            status = recipients_data[0].get("status", "Unknown")
            cost = recipients_data[0].get("cost", "Unknown")

            log.info(
                "AT delivery status=%s cost=%s",
                status,
                cost
            )

            success = status in ("Success", "Sent")

        else:
            status = response.get(
                "SMSMessageData", {}
            ).get("Message", "Unknown")

            success = False

        return {
            "success": success,
            "status": status,
            "raw": response
        }

    except Exception as e:
        log.error("AT SMS send failed: %s", e)

        return {
            "success": False,
            "status": "error",
            "error": str(e)
        }


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/sms", methods=["POST"])
def receive_sms():
    """Africa's Talking inbound SMS webhook."""
    sender       = request.form.get("from", "").strip()
    message_text = request.form.get("text", "").strip()

    log.info("Inbound SMS — from=%s  text=%r", sender, message_text)

    if not sender or not message_text:
        return "Missing sender or message.", 400

    # 1. Generate AI response
    ai_response = get_ai_response(message_text)
    log.info("AI response generated — to=%s  response=%r", sender, ai_response)

    # 2. Send reply via Africa's Talking
    sms_result = send_sms(recipient=sender, message=ai_response)
    if sms_result["success"]:
        log.info("SMS delivered successfully to %s", sender)
    else:
        log.error("SMS delivery failed to %s: %s", sender, sms_result.get("error") or sms_result.get("status"))

    # 3. Save to database regardless of SMS delivery outcome
    timestamp = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
    save_query(
        phone_number=sender,
        user_query=message_text,
        gemini_response=ai_response,
        timestamp=timestamp,
    )

    # AT webhook expects a 200 plain-text acknowledgement
    return "OK", 200, {"Content-Type": "text/plain"}


@app.route("/testsms")
def test_sms():
    """
    Test outbound SMS independently.
    Usage: GET /testsms?to=+265XXXXXXXXX&msg=Hello
    """
    recipient = request.args.get("to", "").strip()
    message   = request.args.get("msg", "Voogle test message — outbound SMS is working!").strip()

    if not recipient:
        return jsonify({
            "error": "Provide ?to=+265XXXXXXXXX",
            "example": "/testsms?to=+265982838730&msg=Hello+Voogle"
        }), 400

    log.info("Test SMS — to=%s  msg=%r", recipient, message)
    result = send_sms(recipient=recipient, message=message)
    return jsonify(result)


@app.route("/admin")
def admin_dashboard():
    queries = get_all_queries()
    return render_template("dashboard.html", queries=queries)


@app.route("/admin/api/queries")
def api_queries():
    queries = get_all_queries()
    return jsonify(queries)

@app.route("/debug")
def debug():
    return jsonify({
        "gemini_key_exists": bool(GEMINI_API_KEY),
        "gemini_key_preview": (
            GEMINI_API_KEY[:6] + "..."
        ) if GEMINI_API_KEY else None,
        "model_name": "gemini-3.7-flash",
        "at_username": AT_USERNAME,
        "at_sender_id": AT_SENDER_ID,
        "at_api_key_exists": bool(AT_API_KEY),
        "at_api_key_preview": (
            AT_API_KEY[:6] + "..."
        ) if AT_API_KEY else None,
    })


@app.route("/health")
def health():
    return {"status": "ok", "app": "Voogle"}, 200


@app.route("/models")
def models():
    return {
        "models": [
            m.name
            for m in genai.list_models()
        ]
    }


@app.route("/")
def index():
    return (
        "<h2>Voogle is running.</h2>"
        "<p>Inbound webhook: <code>POST /sms</code></p>"
        "<p>Test outbound: <code>GET /testsms?to=+265XXXXXXXXX</code></p>"
        "<p><a href='/admin'>Admin Dashboard</a></p>"
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
