from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from config import ROOTKEEPER

def get_cluster_router():
    router = APIRouter()

    @router.get("/cluster-state")
    async def get_cluster_state():
        return RedirectResponse(url=f"{ROOTKEEPER['node_url']}/cluster-state")

    return router
