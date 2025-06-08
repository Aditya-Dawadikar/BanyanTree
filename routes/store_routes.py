from fastapi import APIRouter, HTTPException
from models import AddRecordRequest, AddRecordResponse, GetRecordResponse
from controllers.store_controller import create_store_controller
from config import NODE_ROLES
from fastapi.responses import RedirectResponse

def get_store_router(node):
    router = APIRouter()
    add_record, get_record = create_store_controller(node)

    @router.post("/store/add", response_model=AddRecordResponse)
    async def add_record_route(req: AddRecordRequest):
        if node.curr_role != NODE_ROLES["LEADER"]:
            if node.current_leader and node.current_leader in node.peers:
                leader_url = node.peers[node.current_leader]["peer_url"]
                return RedirectResponse(url=f"{leader_url}/store/add", status_code=307)
            raise HTTPException(status_code=503, detail="No leader available")

        return add_record(req)

    @router.get("/store/get/{key}", response_model=GetRecordResponse)
    async def get_record_route(key: str):
        result = get_record(key)
        if not result:
            raise HTTPException(status_code=404, detail="Key not found")
        return result

    return router
