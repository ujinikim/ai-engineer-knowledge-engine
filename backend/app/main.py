from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.settings import settings


app = FastAPI(title="AI Engineer Knowledge Engine")
local_dev_origins = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://0.0.0.0:5173",
    *settings.cors_origins,
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(local_dev_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
