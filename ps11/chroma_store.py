import os
from datetime import datetime, timezone
import chromadb

_COLLECTION = "eda_reports"

class ChromaStore:
    def __init__(self) -> None:
        mode = os.environ.get("CHROMA_MODE", "memory")
        if mode == "memory":
            self._client = chromadb.Client()
        else:
            persist_dir = os.environ.get("CHROMA_PERSIST_DIR", "./data/chroma")
            self._client = chromadb.PersistentClient(path=persist_dir)
        self._col = self._client.get_or_create_collection(_COLLECTION)

    def store_report(
        self,
        dataset_name: str,
        row_count: int,
        col_count: int,
        summary_json: str,
    ) -> None:
        doc_id = f"{dataset_name}-{datetime.now(timezone.utc).isoformat()}"
        self._col.add(
            documents=[summary_json],
            metadatas=[{
                "dataset_name": dataset_name,
                "row_count":    row_count,
                "col_count":    col_count,
                "timestamp":    datetime.now(timezone.utc).isoformat(),
            }],
            ids=[doc_id],
        )

    def search_similar(self, query: str, n: int = 3) -> list[dict]:
        count = self._col.count()
        if count == 0:
            return []
        results = self._col.query(
            query_texts=[query],
            n_results=min(n, count),
        )
        out = []
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            out.append({"summary": doc, "meta": meta})
        return out
