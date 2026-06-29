"""
Supabase Client Helper

Provides a reusable Supabase client instance initialized with the service key,
which bypasses Row-Level Security for backend operations.

Related: Requirements 1.1, 1.2, 6.1
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


def get_supabase_client() -> Client:
    """
    Create a Supabase client using the service key.

    The service key bypasses RLS policies, allowing the backend to perform
    operations on behalf of any user.

    Returns:
        Authenticated Supabase client

    Raises:
        ValueError: If required environment variables are not set
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError(
            "Missing required environment variables: SUPABASE_URL and/or SUPABASE_SERVICE_KEY"
        )

    return create_client(supabase_url, supabase_key)
