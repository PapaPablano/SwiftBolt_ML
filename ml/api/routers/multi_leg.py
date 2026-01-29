"""Multi-leg strategies proxy — forward requests to Supabase Edge functions.

So the client can call FastAPI for multi-leg (list, detail, create, update,
close-leg, close-strategy, templates, delete) and FastAPI forwards to Edge.
Requires SUPABASE_URL and Supabase key in FastAPI env.
"""

import logging
import sys
from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

# Add ml root for imports
ml_dir = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ml_dir))

logger = logging.getLogger(__name__)
router = APIRouter()

EDGE_PATHS = [
    "multi-leg-list",
    "multi-leg-detail",
    "multi-leg-create",
    "multi-leg-update",
    "multi-leg-close-leg",
    "multi-leg-close-strategy",
    "multi-leg-templates",
    "multi-leg-delete",
]


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


async def _proxy(request: Request, edge_path: str):
    """Forward request to Supabase Edge function; return response."""
    try:
        base = _edge_base()
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Multi-leg proxy requires SUPABASE_URL.") from None
    url = f"{base}/{edge_path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"
    headers = {}
    for name in ("authorization", "content-type", "apikey"):
        v = request.headers.get(name)
        if v:
            headers[name] = v
    # Use Supabase key from env if client didn't send auth (e.g. server-to-server)
    if "authorization" not in headers:
        try:
            from config.settings import settings
            key = getattr(settings, "supabase_key", None) or getattr(settings, "supabase_service_role_key", None)
            if key:
                headers["authorization"] = f"Bearer {key}"
                headers["apikey"] = key
        except Exception:
            pass
    body = None
    if request.method in ("POST", "PATCH", "PUT"):
        body = await request.body()
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.request(
            request.method,
            url,
            headers=headers,
            content=body,
        )
    return Response(
        content=r.content,
        status_code=r.status_code,
        headers={k: v for k, v in r.headers.items() if k.lower() in ("content-type", "content-length")},
    )


# Register one proxy route per Edge path (all methods)
for _path in EDGE_PATHS:
    def _make_handler(edge_path: str):
        async def _handler(request: Request):
            return await _proxy(request, edge_path)
        return _handler
    router.add_api_route(
        f"/{_path}",
        _make_handler(_path),
        methods=["GET", "POST", "PATCH", "DELETE"],
        name=f"multi_leg_{_path.replace('-', '_')}",
    )
