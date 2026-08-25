import os
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

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

    supabase.table("queries").insert({
        "phone_number": phone_number,
        "user_query": user_query,
        "gemini_response": gemini_response,
        "timestamp": timestamp
    }).execute()


def get_all_queries():

    response = (
        supabase
        .table("queries")
        .select("*")
        .order("id", desc=True)
        .execute()
    )

    return response.data
