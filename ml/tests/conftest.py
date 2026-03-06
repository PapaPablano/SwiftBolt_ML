"""
Pytest configuration for SwiftBolt ML test suite.

Patches module-level Supabase initialization so that importing any module
that calls supabase.create_client at module scope (e.g. supabase_db.py line
``db = SupabaseDatabase()``) does not fail during pytest collection in CI
environments where real credentials are not available.

All unit tests that exercise database-touching code must mock ``db`` /
``supabase.create_client`` themselves — this patch only prevents collection
errors; it does not provide a usable client.
"""

import os
from unittest.mock import MagicMock, patch

# Ensure dummy credentials are present before any src.* imports so that
# pydantic-settings (Settings class) can construct without raising a
# ValidationError for the required ``supabase_url`` field.
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "placeholder-key-for-ci")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "placeholder-key-for-ci")

# Patch create_client at conftest *import* time (before any test module is
# collected) so that the module-level ``db = SupabaseDatabase()`` call in
# supabase_db.py does not crash with a network/auth error.
_supabase_patch = patch("supabase.create_client", return_value=MagicMock())
_supabase_patch.start()
