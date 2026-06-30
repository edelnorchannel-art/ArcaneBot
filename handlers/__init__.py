from aiogram import Router

from handlers.start import router as start_router
from handlers.upload import router as upload_router
from services.access_service import AccessMiddleware

router = Router()
router.message.middleware(AccessMiddleware())
router.callback_query.middleware(AccessMiddleware())
router.include_router(start_router)
router.include_router(upload_router)
