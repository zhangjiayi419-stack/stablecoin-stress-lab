"""Bounded public demo requests; deliberately not a production WAF."""
import os
import time
from collections import defaultdict, deque
from threading import BoundedSemaphore
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

PUBLIC_DEMO = os.getenv('PUBLIC_DEMO', '0') == '1'
EXPENSIVE = {'/api/quote', '/api/agents/simulate', '/api/agents/phase-diagram', '/api/portfolio/stress', '/api/risk-assistant/analyze'}


class PublicDemoLimits(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.requests = defaultdict(deque)
        self.slots = BoundedSemaphore(2)

    async def dispatch(self, request, call_next):
        if not PUBLIC_DEMO:
            return await call_next(request)
        if request.method == 'POST' and request.url.path == '/api/pool-snapshots':
            return JSONResponse({'detail':'Historical data uploads are disabled in the public demo.'},status_code=403)
        if request.method != 'POST' or request.url.path not in EXPENSIVE:
            return await call_next(request)
        if len(await request.body()) > 16384:
            return JSONResponse({'detail':'Request exceeds the demo size limit.'},status_code=413)
        now = time.monotonic()
        if len(self.requests) >= 5000:
            self.requests = defaultdict(deque,{k:v for k,v in self.requests.items() if v and v[-1] > now-60})
            if len(self.requests) >= 5000:
                return JSONResponse({'detail':'Demo is busy. Please retry shortly.'},status_code=429)
        key = request.client.host if request.client else 'unknown'
        queue = self.requests[key]
        while queue and queue[0] <= now-60:
            queue.popleft()
        if len(queue) >= 12:
            return JSONResponse({'detail':'Demo limit: 12 calculations per minute. Please wait.'},status_code=429,headers={'Retry-After':'60'})
        if not self.slots.acquire(blocking=False):
            return JSONResponse({'detail':'Two scenarios are already running. Please retry shortly.'},status_code=429,headers={'Retry-After':'5'})
        queue.append(now)
        try:
            return await call_next(request)
        finally:
            self.slots.release()
