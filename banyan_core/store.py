from datetime import datetime, timezone
from config import RECORD_STATUS


class Store:
    def __init__(self):
        self.records = {}

    def add_record(self, key, value):
        timestamp = datetime.now(timezone.utc).timestamp()

        if self.records.get(key, None) is None:
            # add new record
            self.records[key] = {
                "key": key,
                "value": value,
                "status": RECORD_STATUS["UNCOMMITTED"],
                "is_deleted": False,
                "created_at": timestamp,
                "last_updated_at": timestamp,
                "last_committed_at": None
            }
        else:
            # update record
            self.records[key]["value"] = value
            self.records[key]["last_updated_at"] = timestamp
            self.records[key]["status"] = RECORD_STATUS["UNCOMMITTED"]

    def delete_record(self, key):
        if key not in self.records:
            return
        else:
            timestamp = datetime.now(timezone.utc).timestamp()
            self.records[key]["is_deleted"] = True
            self.records[key]["last_updated_at"] = timestamp

    def commit_record(self, key):
        if key not in self.records:
            return
        else:
            timestamp = datetime.now(timezone.utc).timestamp()
            self.records[key]["status"] = RECORD_STATUS["COMMITTED"]
            self.records[key]["last_committed_at"] = timestamp

    def get_record(self, key, committed_only=True):
        record = self.records.get(key, None)
        if record is None or (record["is_deleted"]) or (committed_only and record["status"] != RECORD_STATUS["COMMITTED"]):
            return None
        return record
