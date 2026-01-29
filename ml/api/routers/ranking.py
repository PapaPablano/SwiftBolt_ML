"""Ranking trigger proxy — forward POST to Supabase Edge trigger-ranking-job.

So the client can call FastAPI to refresh options_ranks when conditions change
(symbol change, pull-to-refresh). FastAPI forwards to Edge which computes and
saves Momentum-Value-Greeks rankings. Requires SUPABASE_URL and Supabase key.
"""

import logging
import sys
from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

ml_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ml_dir))

logger = logging.getLogger(__name__)
router = APIRouter()

EDGE_PATH = "trigger-ranking-job"


def _edge_base() -> str:
    try:
        from config.settings import settings
        url = (getattr(settings, "supabase_url", None) or "").rstrip("/")
        if not url:
            raise ValueError("SUPABASE_URL not set")
        return f"{url}/functions/v1"
    except Exception as e:
        logger.warning("Supabase URL unavailable: %s", e)
        raise


async def _proxy(request: Request) -> Response:
    try:
        base = _edge_base()
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="Ranking trigger requires SUPABASE_URL.",
        ) from None
    url = f"{base}/{EDGE_PATH}"
    headers = {}
    for name in ("authorization", "content-type", "apikey"):
        v = request.headers.get(name)
        if v:
            headers[name] = v
    if "authorization" not in headers:
        try:
            from config.settings import settings
            key = getattr(settings, "supabase_key", None) or getattr(
                settings, "supabase_service_role_key", None
            )
            if key:
                headers["authorization"] = f"Bearer {key}"
                headers["apikey"] = key
        except Exception:
            pass
    body = await request.body()
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, headers=headers, content=body)
    # Do not copy Content-Length: Starlette sets it from len(content). Copying upstream
    # Content-Length can cause "Response content longer than Content-Length" if upstream
    # was wrong or encoding differs.
    return Response(
        content=r.content,
        status_code=r.status_code,
        headers={k: v for k, v in r.headers.items() if k.lower() == "content-type"},
    )


@router.post(f"/{EDGE_PATH}")
async def trigger_ranking_job(request: Request):
    """Proxy POST to Supabase Edge trigger-ranking-job. Body: { \"symbol\": \"AAPL\" }."""
    return await _proxy(request)
