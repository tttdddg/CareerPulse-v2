from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .routers import router

app = FastAPI()

# Handle browser preflight (OPTIONS) for cross-origin frontend calls.
# Allow localhost + common private-network dev origins.
CORS_ORIGIN_REGEX = (
    r"^https?://((localhost|127\\.0\\.0\\.1)"
    r"|((10|192\\.168)\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})"
    r"|(172\\.(1[6-9]|2\\d|3[0-1])\\.\\d{1,3}\\.\\d{1,3}))(:\\d+)?$"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def preflight_fallback(request: Request, call_next):
    # Fallback: respond to OPTIONS even if upstream routing/middleware order changes.
    if request.method == "OPTIONS":
        origin = request.headers.get("origin", "")
        response = Response(status_code=204)
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = request.headers.get(
            "access-control-request-headers", "Authorization,Content-Type"
        )
        response.headers["Access-Control-Max-Age"] = "86400"
        return response

    return await call_next(request)


app.include_router(router)
