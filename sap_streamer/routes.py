from fastapi import APIRouter
from elasticsearch import Elasticsearch
from fastapi import Query, Path
from typing import List, Optional

def get_cluster_router(es: Elasticsearch):
    router = APIRouter()

    @router.get("/logs/{topic}")
    async def get_cluster_logs(topic: str = Path(..., description="Kafka topic (e.g., 'raft-logs')"),
                                skip: int = Query(0, ge=0),
                                limit: int = Query(50, le=500),
                                start_time: Optional[str] = Query(None, description="Start timestamp (ISO format)"),
                                end_time: Optional[str] = Query(None, description="End timestamp (ISO format)"),
                                keywords: Optional[List[str]] = Query(None, description="List of keywords (OR)")
                            ):
        index_name = f"{topic}"

        # Build ES query
        must_clauses = []

        # Time range filter
        if start_time or end_time:
            time_filter = {}
            if start_time:
                time_filter["gte"] = start_time
            if end_time:
                time_filter["lte"] = end_time
            must_clauses.append({"range": {"timestamp": time_filter}})

        # Keyword matching (OR logic using 'should')
        if keywords:
            should_clauses = [{"match": {"message": kw}} for kw in keywords]
            must_clauses.append({"bool": {"should": should_clauses, "minimum_should_match": 1}})

        query_body = {"bool": {"must": must_clauses}} if must_clauses else {"match_all": {}}

        # Run ES query
        try:
            result = es.search(
                index=index_name,
                query=query_body,
                from_=skip,
                size=limit,
                sort=[{"timestamp": {"order": "desc"}}]
            )
            return [hit["_source"] for hit in result["hits"]["hits"]]
        except Exception as e:
            return {"error": str(e)}

    return router
