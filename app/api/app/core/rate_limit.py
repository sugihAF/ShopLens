"""Rate limiting configuration."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Rate limiter — uses Redis as storage backend if available
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=[],
)
