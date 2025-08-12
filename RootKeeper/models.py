from pydantic import BaseModel
from typing import List

class NodeRecord(BaseModel):
    name: str
    url: str

class InputNodeRecords(BaseModel):
    nodes: List[NodeRecord]