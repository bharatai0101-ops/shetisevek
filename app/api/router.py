from fastapi import APIRouter

from app.api.routes.commerce import router as commerce_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.health import router as health_router
from app.api.routes.questions import router as questions_router
from app.api.routes.users import router as users_router
from app.api.routes.whatsapp import router as whatsapp_router

router = APIRouter()
router.include_router(health_router)
router.include_router(whatsapp_router)

router.include_router(commerce_router)

router.include_router(users_router)

router.include_router(questions_router)

router.include_router(dashboard_router)
