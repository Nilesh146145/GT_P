from __future__ import annotations

from fastapi import APIRouter, Depends

from app.routers.decomposition._dependencies import require_enterprise_user
from app.routers.decomposition.action import router as actions_router
from app.routers.decomposition.checklist import router as checklist_router
from app.routers.decomposition.plan_review import router as plan_review_router
from app.routers.decomposition.plans import router as plans_router
from app.routers.decomposition.revised import router as revised_router
from app.routers.decomposition.revision import router as revision_router
from app.routers.decomposition.revision_details import router as revision_detail_router
from app.routers.decomposition.summary import router as summary_router
from app.routers.decomposition.task_details import router as task_detail_router
from app.routers.decomposition.tasks import router as task_router

decomposition_router = APIRouter(
    prefix="/enterprise/decomposition",
    dependencies=[Depends(require_enterprise_user)],
)

decomposition_router.include_router(plans_router)
decomposition_router.include_router(plan_review_router)
decomposition_router.include_router(task_router, prefix="/plans", tags=["Tasks"])
decomposition_router.include_router(checklist_router, prefix="/plans", tags=["Checklist"])
decomposition_router.include_router(summary_router, prefix="/plans", tags=["Summary"])
decomposition_router.include_router(task_detail_router, prefix="/plans", tags=["Task Detail"])
decomposition_router.include_router(revision_router, prefix="/plans", tags=["Revision"])
decomposition_router.include_router(revised_router, prefix="/plans", tags=["Revised Plan"])
decomposition_router.include_router(revision_detail_router, prefix="/plans", tags=["Revision Detail"])
decomposition_router.include_router(actions_router)

__all__ = ["decomposition_router"]
