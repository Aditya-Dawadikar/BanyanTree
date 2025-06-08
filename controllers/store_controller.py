from models import AddRecordRequest, AddRecordResponse, GetRecordResponse
from config import STATUS_MAP
from fastapi.exceptions import HTTPException

def create_store_controller(node):
    def add_record(req: AddRecordRequest) -> AddRecordResponse:
        node.handle_client_write(req.key, req.value)
        return AddRecordResponse(
            success=True,
            message="Record accepted for replication",
            key=req.key
        )

    def get_record(key: str) -> GetRecordResponse:
        record = node.store.records.get(key)
        if record is None:
            raise HTTPException(status_code=404, detail="Key not found")

        return GetRecordResponse(
            key=record["key"],
            value=record["value"],
            status=STATUS_MAP[record["status"]],
            is_deleted=record["is_deleted"],
            created_at=record["created_at"],
            last_updated_at=record["last_updated_at"],
            last_committed_at=record["last_committed_at"]
        )

    return add_record, get_record
