from fastapi import APIRouter
from app.api.auth import auth_router
from app.api.user import user_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(user_router, prefix="/user", tags=["user"])
