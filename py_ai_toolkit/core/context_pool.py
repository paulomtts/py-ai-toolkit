import math
import sqlite3
import struct
from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel


class StoredChunk(BaseModel):
    id: str
    session_id: str
    text: str
    embedding: list[float]
    created_at: datetime
    access_count: int = 0


class ContextPool:
    def __init__(self, db_path: str, embedding_dim: int = 1536):
        self.db_path = db_path
        self.embedding_dim = embedding_dim
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding BLOB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON chunks(session_id)")
        conn.commit()
        conn.close()

    async def store(self, text: str, embedding: list[float], session_id: str) -> str:
        chunk_id = uuid4().hex
        embedding_blob = self._serialize_embedding(embedding)

        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO chunks (id, session_id, text, embedding) VALUES (?, ?, ?, ?)",
            (chunk_id, session_id, text, embedding_blob),
        )
        conn.commit()
        conn.close()
        return chunk_id

    def _serialize_embedding(self, embedding: list[float]) -> bytes:
        return struct.pack(f"{len(embedding)}f", *embedding)

    def _deserialize_embedding(self, blob: bytes) -> list[float]:
        count = len(blob) // 4
        return list(struct.unpack(f"{count}f", blob))

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        session_id: str,
        top_k: int = 5,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
    ) -> list[StoredChunk]:
        chunks = self._get_session_chunks(session_id)
        if not chunks:
            return []

        vector_scores = self._vector_search(query_embedding, chunks)
        bm25_scores = self._bm25_search(query_text, chunks)

        combined: dict[str, float] = {}
        for chunk_id, score in vector_scores.items():
            combined[chunk_id] = score * vector_weight
        for chunk_id, score in bm25_scores.items():
            combined[chunk_id] = combined.get(chunk_id, 0) + score * bm25_weight

        sorted_ids = sorted(combined, key=lambda x: combined[x], reverse=True)[:top_k]
        return [self._get_chunk_by_id(chunk_id) for chunk_id in sorted_ids]

    def _vector_search(
        self,
        query_embedding: list[float],
        chunks: list[StoredChunk],
    ) -> dict[str, float]:
        scores = {}
        for chunk in chunks:
            score = self._cosine_similarity(query_embedding, chunk.embedding)
            scores[chunk.id] = score
        return self._normalize_scores(scores)

    def _bm25_search(
        self,
        query_text: str,
        chunks: list[StoredChunk],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> dict[str, float]:
        query_terms = query_text.lower().split()
        avg_len = sum(len(c.text.split()) for c in chunks) / len(chunks) if chunks else 1

        scores: dict[str, float] = {}
        for chunk in chunks:
            chunk_terms = chunk.text.lower().split()
            chunk_len = len(chunk_terms)
            score = 0.0

            for term in query_terms:
                tf = chunk_terms.count(term)
                df = sum(1 for c in chunks if term in c.text.lower())
                idf = math.log((len(chunks) - df + 0.5) / (df + 0.5) + 1)

                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * chunk_len / avg_len)
                score += idf * numerator / denominator

            scores[chunk.id] = score

        return self._normalize_scores(scores)

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    def _normalize_scores(self, scores: dict[str, float]) -> dict[str, float]:
        if not scores:
            return scores
        max_score = max(scores.values())
        if max_score == 0:
            return scores
        return {k: v / max_score for k, v in scores.items()}

    def _get_session_chunks(self, session_id: str) -> list[StoredChunk]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM chunks WHERE session_id = ?", (session_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            StoredChunk(
                id=row["id"],
                session_id=row["session_id"],
                text=row["text"],
                embedding=self._deserialize_embedding(row["embedding"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                access_count=row["access_count"],
            )
            for row in rows
        ]

    def _get_chunk_by_id(self, chunk_id: str) -> StoredChunk:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            raise ValueError(f"Chunk {chunk_id} not found")

        return StoredChunk(
            id=row["id"],
            session_id=row["session_id"],
            text=row["text"],
            embedding=self._deserialize_embedding(row["embedding"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            access_count=row["access_count"],
        )
