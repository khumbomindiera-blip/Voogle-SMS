import os
import datetime
from flask import Flask, request, render_template, jsonify
from groq import Groq
from duckduckgo_search import DDGS

app = Flask(__name__)

# Configure Groq client
GROQ_API_KEY = os.environ.get("Voogle")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

GROQ_MODEL = "llama-3.3-70b-versatile"

# Initialize database on startup
from database import init_db, save_query, get_all_queries
with app.app_context():
    init_db()

# Keywords that signal a current-events / real-time query
CURRENT_EVENT_KEYWORDS = [
    "news", "today", "latest", "current", "recent", "now", "tonight",
    "this week", "this month", "weather", "trending", "happening",
    "update", "score", "results", "election", "match", "game",
    "breaking", "died", "arrested", "launched", "announced", "released",
    "yesterday", "last night", "this morning",
]


def is_current_events_query(text: str) -> bool:
    """Return True if the query is likely asking about real-time information."""
    lower = text.lower()
    return any(kw in lower for kw in CURRENT_EVENT_KEYWORDS)


def search_web(query: str, max_results: int = 4) -> str:
    """Fetch top DuckDuckGo results and return them as a context string."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return ""
        snippets = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            snippets.append(f"- {title}: {body}")
        return "\n".join(snippets)
    except Exception as e:
        return ""


def get_ai_response(message: str) -> str:
    """Return an SMS-friendly AI response, with web grounding for current-events queries."""
    if not client:
        return "Error: Groq API key is not configured."

    try:
        if is_current_events_query(message):
            # Ground the answer with live search results
            context = search_web(message)
            if context:
                system_prompt = (
                    "You are a helpful assistant replying via SMS. "
                    "Use the search results below to answer the user's question. "
                    "Be concise — 2 to 4 sentences maximum. Plain text only, no markdown."
                )
                user_content = (
                    f"Search results:\n{context}\n\n"
                    f"Question: {message}"
                )
            else:
                # Search failed — fall back to plain response
                system_prompt = (
                    "You are a helpful assistant replying via SMS. "
                    "Be concise — 2 to 4 sentences maximum. Plain text only, no markdown."
                )
                user_content = message
        else:
            system_prompt = (
                "You are a helpful assistant replying via SMS. "
                "Be concise — 2 to 4 sentences maximum. Plain text only, no markdown."
            )
            user_content = message

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"Error: {str(e)}"


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

    ai_response = get_ai_response(message_text)

    timestamp = datetime.datetime.now().isoformat(sep=" ", timespec="seconds")
    save_query(
        phone_number=sender,
        user_query=message_text,
        gemini_response=ai_response,
        timestamp=timestamp,
    )

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
