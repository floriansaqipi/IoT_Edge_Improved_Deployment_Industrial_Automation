from __future__ import annotations

import os
from typing import Protocol

from .processor import TableWrite


class TableWriter(Protocol):
    def write(self, write: TableWrite) -> None:
        """Persist one table write."""


class CloudTableWriter:
    def __init__(self, connection_string: str) -> None:
        from azure.data.tables import TableServiceClient

        self.service = TableServiceClient.from_connection_string(connection_string)
        self._clients: dict[str, object] = {}

    @classmethod
    def from_env(cls) -> "CloudTableWriter":
        connection_string = os.getenv("CLOUD_RESULTS_STORAGE_CONNECTION_STRING") or os.getenv("AzureWebJobsStorage")
        if not connection_string:
            raise ValueError("CLOUD_RESULTS_STORAGE_CONNECTION_STRING or AzureWebJobsStorage is required.")
        return cls(connection_string)

    def write(self, write: TableWrite) -> None:
        from azure.data.tables import UpdateMode

        client = self._client(write.table_name)
        client.upsert_entity(mode=UpdateMode.MERGE, entity=write.entity)

    def _client(self, table_name: str):
        if table_name not in self._clients:
            self.service.create_table_if_not_exists(table_name)
            self._clients[table_name] = self.service.get_table_client(table_name)
        return self._clients[table_name]
