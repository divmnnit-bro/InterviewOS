from fastapi import APIRouter

from app.api.routes import (
    ai,
    analytics,
    auth,
    booking,
    drives,
    evaluations,
    interviews,
    jobs,
    me,
    pipeline,
    rescue,
    rooms,
    schedule,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(drives.router)
api_router.include_router(rooms.router)
api_router.include_router(schedule.router)
api_router.include_router(rescue.router)
api_router.include_router(booking.router)
api_router.include_router(interviews.router)
api_router.include_router(evaluations.router)
api_router.include_router(pipeline.router)
api_router.include_router(ai.router)
api_router.include_router(analytics.router)
api_router.include_router(jobs.router)
