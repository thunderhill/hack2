"""ChromaDB store for persisting and searching past analyses."""

import json
import uuid
from datetime import datetime

import chromadb


class ChromaStore:
    def __init__(self, collection_name: str, persist_dir: str = "./data/chroma"):
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, input_text: str, result: dict, model_key: str = "") -> str:
        doc_id = str(uuid.uuid4())
        self._collection.add(
            ids=[doc_id],
            documents=[input_text],
            metadatas=[{
                "result": json.dumps(result),
                "model_key": model_key,
                "timestamp": datetime.now().isoformat(),
            }],
        )
        return doc_id

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        count = self._collection.count()
        if count == 0:
            return []
        results = self._collection.query(
            query_texts=[query],
            n_results=min(n_results, count),
        )
        items = []
        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            items.append({
                "id": doc_id,
                "input": results["documents"][0][i],
                "result": json.loads(meta["result"]),
                "model_key": meta.get("model_key", ""),
                "timestamp": meta.get("timestamp", ""),
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })
        return items

    def get_recent(self, n: int = 10) -> list[dict]:
        all_data = self._collection.get(include=["documents", "metadatas"])
        items = []
        for i, doc_id in enumerate(all_data["ids"]):
            meta = all_data["metadatas"][i]
            items.append({
                "id": doc_id,
                "input": all_data["documents"][i],
                "result": json.loads(meta["result"]),
                "model_key": meta.get("model_key", ""),
                "timestamp": meta.get("timestamp", ""),
            })
        items.sort(key=lambda x: x["timestamp"], reverse=True)
        return items[:n]

    def count(self) -> int:
        return self._collection.count()
