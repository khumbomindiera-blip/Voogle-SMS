import os
import requests
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()

print("========== SUPABASE DEBUG ==========")
print("SUPABASE_URL repr:", repr(SUPABASE_URL))
print("SUPABASE_KEY exists:", bool(SUPABASE_KEY))
print("====================================")

# Test direct connectivity to Supabase
try:
    r = requests.get(SUPABASE_URL, timeout=10)
    print("SUPABASE TEST STATUS:", r.status_code)
except Exception as e:
    print("SUPABASE TEST FAILED:", str(e))

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


def init_db():
    """
    No-op.
    Table already exists in Supabase.
    """
    pass


def save_query(phone_number, user_query, gemini_response, timestamp):
    try:
        response = (
            supabase
            .table("queries")
            .insert({
                "phone_number": phone_number,
                "user_query": user_query,
                "gemini_response": gemini_response,
                "timestamp": timestamp
            })
            .execute()
        )

        print("SAVE QUERY SUCCESS")
        return response

    except Exception as e:
        print("SAVE QUERY ERROR:", str(e))
        raise


def get_all_queries():
    try:
        print("Fetching queries from Supabase...")

        response = (
            supabase
            .table("queries")
            .select("*")
            .order("id", desc=True)
            .execute()
        )

        print("QUERY FETCH SUCCESS")
        return response.data

    except Exception as e:
        print("QUERY FETCH ERROR:", str(e))
        raise
