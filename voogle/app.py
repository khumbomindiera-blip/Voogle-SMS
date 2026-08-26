import os
import logging
import datetime
import requests
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
    model = genai.GenerativeModel("models/gemini-3.6-flash")
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
            f"- {r.get('title','')}: {r.get('body','')}"
            for r in results
        )

    except Exception as e:
        log.warning("Web search failed: %s", e)
        return ""

DISTRICTS = {
    "blantyre": (-15.7861, 35.0058),
    "lilongwe": (-13.9833, 33.7833),
    "mzuzu": (-11.4656, 34.0207),
    "zomba": (-15.3833, 35.3333),
    "mangochi": (-14.4781, 35.2645),
    "salima": (-13.7804, 34.4587),
    "kasungu": (-13.0333, 33.4833),
    "karonga": (-9.9333, 33.9333),
    "mulanje": (-16.0333, 35.5000),
    "mchinji": (-13.8000, 32.8833),
    "dedza": (-14.3833, 34.3333),
    "ntcheu": (-14.8167, 34.6333),
    "balaka": (-14.9833, 34.9500),
    "phalombe": (-15.8000, 35.6500),
    "chikwawa": (-16.0333, 34.8000),
    "nsanje": (-16.9167, 35.2667),
    "rumphi": (-11.0167, 33.8500),
    "nkhatabay": (-11.6000, 34.3000),
    "likoma": (-12.0500, 34.7333)
}
def get_weather(location="blantyre"):

    location = location.lower().strip()

    if location not in DISTRICTS:
        return f"Location '{location}' not found in Malawi."

    lat, lon = DISTRICTS[location]

    try:

        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}"
            f"&longitude={lon}"
            f"&current=temperature_2m,precipitation,rain"
        )

        r = requests.get(url, timeout=10)

        data = r.json()

        current = data["current"]

        temp = current.get("temperature_2m", "N/A")
        rain = current.get("rain", 0)
        precip = current.get("precipitation", 0)

        return (
            f"Current weather in {location.title()}:\n"
            f"Temperature: {temp}°C\n"
            f"Rain: {rain} mm\n"
            f"Precipitation: {precip} mm"
        )

    except Exception as e:
        return f"Weather service unavailable: {e}"

def get_ai_response(message: str):

    if not model:
        return "Error: Gemini API key not configured."

    try:

        lower = message.lower()

        # Weather / climate questions
        weather_keywords = [
            "weather",
            "rain",
            "temperature",
            "flood",
            "storm",
            "heat",
            "climate",
            "forecast",
            "mvula",
            "kutentha",
            "nyengo"
        ]

        if any(word in lower for word in weather_keywords):

            district_found = "blantyre"

            for district in DISTRICTS.keys():
                if district in lower:
                    district_found = district
                    break

            weather_data = get_weather(district_found)

            prompt = f"""
You are Voogle Climate AI for Malawi.

Weather Data:

{weather_data}

User Question:
{message}

Rules:
- Maximum 4 short SMS-friendly sentences.
- Use the weather data above.
- Give practical advice.
- Mention the district.
- If flood risk cannot be determined, say so.
"""

            response = model.generate_content(prompt)
            return response.text.strip()

        # Normal questions
        context = ""

        if is_current_events_query(message):
            context = search_web(message)

        prompt = f"""
You are Voogle AI Assistant for Malawi.

Search Results:
{context}

Question:
{message}

Rules:
- Maximum 4 short sentences.
- Plain SMS format.
"""

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        return f"Error: {str(e)}"

def send_sms(recipient: str, message: str) -> dict:
    """
    Send an SMS via SMSMobileAPI and return a result dict.
    """

    import os
    import requests

    sms_api_key = os.getenv("SMS_API_KEY")

    if not sms_api_key:
        return {
            "success": False,
            "status": "disabled",
            "error": "SMSMobileAPI key not configured"
        }

    payload = {
        "apikey": sms_api_key,
        "recipients": recipient,
        "message": message
    }

    log.info("SMSMobileAPI request payload: %s", payload)

    try:
        response = requests.get(
            "https://api.smsmobileapi.com/sendsms/",
            params=payload,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

        log.info("SMSMobileAPI response: %s", data)

        result = data.get("result", {})

        error_code = str(result.get("error", "1"))
        sent = str(result.get("sent", "0"))
        status = result.get("note", "Unknown")

        success = (
            error_code == "0"
            and sent == "1"
        )

        return {
            "success": success,
            "status": status,
            "raw": data
        }

    except Exception as e:
        log.error("SMSMobileAPI send failed: %s", e)

        return {
            "success": False,
            "status": "error",
            "error": str(e)
        }

@app.route("/ask")
def ask():

    text = request.args.get("text", "")

    return get_ai_response(text)
# ── Routes ────────────────────────────────────────────────────────────────────

import re
import datetime
from flask import jsonify

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/sms", methods=["POST"])
def receive_sms():

    data = request.get_json(silent=True) or {}

    log.info("RAW JSON: %s", data)

    sender = ""
    message_text = ""

    # SMSMobileAPI webhook format
    if data.get("event") == "message.inbound":

        sms_data = data.get("data", {})

        sender = sms_data.get("from", "").strip()
        message_text = sms_data.get("body", "").strip()

    else:
        # Legacy SMS Forwarder support
        raw_text = data.get("key", "")

        match = re.search(
            r"From\s*:\s*(\+?\d+).*?\n(.*)",
            raw_text,
            re.DOTALL
        )

        if match:
            sender = match.group(1).strip()
            message_text = match.group(2).strip()

    log.info(
        "Inbound SMS — from=%s text=%r",
        sender,
        message_text
    )

    if not message_text:
        return jsonify({
            "reply": "Sorry, I could not read your message."
        }), 200

    try:

        log.info("STEP 1: About to call Gemini")

        ai_response = get_ai_response(message_text)

        log.info("STEP 2: Gemini returned")

        if not ai_response:
            ai_response = (
                "Sorry, I could not generate a response right now."
            )

        log.info(
            "AI Reply => %s",
            ai_response
        )

        # Save to database
        timestamp = datetime.datetime.now().isoformat(
            sep=" ",
            timespec="seconds"
        )

        save_query(
            phone_number=sender or "UNKNOWN",
            user_query=message_text,
            gemini_response=ai_response,
            timestamp=timestamp,
        )

        log.info(
            "STEP 3: Saved query to database"
        )

        # Send SMS reply back to user
        if sender:

            sms_result = send_sms(
                recipient=sender,
                message=ai_response
            )

            log.info(
                "STEP 4: SMS send result => %s",
                sms_result
            )

        return jsonify({
            "status": "success",
            "reply": ai_response
        }), 200

    except Exception as e:

        log.exception(
            "SMS processing failed"
        )

        return jsonify({
            "reply": f"System error: {str(e)}"
        }), 200

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
