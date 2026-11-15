
"""
Akshita Melamine — Python Backend
"""

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from rate_limit import limiter

from database import test_database_connection
from enquiry_routes import router as enquiry_router
from image_engine import MAX_UPLOAD_BYTES, process_product_image
from product_routes import router as product_router


BACKEND_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BACKEND_DIR / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


app = FastAPI(
    title="Akshita Melamine API",
    description="Backend API for the Akshita Hospitality catalogue.",
    version="1.0.0",
)

# Configure request rate limiting.
app.state.limiter = limiter
app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)

# Allow the local Next.js frontend to communicate with FastAPI.
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         "http://localhost:3000",
#         "http://127.0.0.1:3000",
#     ],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://akshita-melamine.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount(
    "/media",
    StaticFiles(directory=str(MEDIA_DIR)),
    name="media",
)

# Register API routers.
app.include_router(product_router)
app.include_router(enquiry_router)


@app.get("/")
def home():
    return {"message": "Akshita Melamine API is running."}


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "akshita-melamine-api",
    }


@app.get("/health/database")
def database_health_check():
    try:
        return test_database_connection()
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


@app.post("/dev/product-images")
async def upload_product_image(file: UploadFile = File(...)):
    """Local development endpoint; not for public deployment."""

    try:
        upload_bytes = await file.read(MAX_UPLOAD_BYTES + 1)

        if len(upload_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail="Image size must not exceed 10 MB.",
            )

        try:
            result = process_product_image(upload_bytes)
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            ) from error

        return {
            "message": "Image processed successfully.",
            **result,
        }

    finally:
        await file.close()
