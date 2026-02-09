"""Embedding service for storing review content in Qdrant vector database."""

import asyncio
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """
    Generates embeddings via Gemini and stores them in Qdrant.

    Gracefully degrades if Qdrant or Gemini embedding API is unavailable —
    review ingestion will still succeed, just without vector search capability.
    """

    def __init__(self):
        self._qdrant = None
        self._genai = None

    async def initialize(self) -> None:
        """Connect to Qdrant and verify the collection exists."""
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            self._qdrant = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                timeout=10,
            )

            # Ensure collection exists (768-dim for text-embedding-004)
            collections = await asyncio.to_thread(
                self._qdrant.get_collections
            )
            collection_names = [c.name for c in collections.collections]

            if settings.QDRANT_COLLECTION not in collection_names:
                await asyncio.to_thread(
                    self._qdrant.create_collection,
                    collection_name=settings.QDRANT_COLLECTION,
                    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection: {settings.QDRANT_COLLECTION}")

            # Initialize Gemini for embeddings
            import google.generativeai as genai
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._genai = genai

            logger.info("Embedding service initialized (Qdrant + Gemini embeddings)")

        except Exception as e:
            logger.warning(f"Embedding service unavailable — vector search disabled: {e}")
            self._qdrant = None
            self._genai = None

    async def generate_embedding(self, text: str) -> Optional[list]:
        """Generate an embedding vector for the given text."""
        if not self._genai:
            return None
        try:
            # Truncate very long text to stay within model limits
            truncated = text[:8000] if len(text) > 8000 else text
            result = await asyncio.to_thread(
                self._genai.embed_content,
                model=settings.EMBEDDING_MODEL,
                content=truncated,
            )
            return result["embedding"]
        except Exception as e:
            logger.debug(f"Embedding generation failed: {e}")
            return None

    async def store_review_embedding(
        self,
        review_id: int,
        product_id: int,
        product_name: str,
        reviewer_name: str,
        content: str,
        source_url: str,
    ) -> bool:
        """Generate embedding for review content and store in Qdrant.

        Returns True if stored successfully, False otherwise.
        """
        if not self._qdrant or not self._genai:
            return False

        try:
            vector = await self.generate_embedding(content)
            if not vector:
                return False

            from qdrant_client.models import PointStruct

            point = PointStruct(
                id=review_id,
                vector=vector,
                payload={
                    "review_id": review_id,
                    "product_id": product_id,
                    "product_name": product_name,
                    "reviewer_name": reviewer_name,
                    "content": content[:2000],  # Store truncated content in payload
                    "source_url": source_url,
                },
            )

            await asyncio.to_thread(
                self._qdrant.upsert,
                collection_name=settings.QDRANT_COLLECTION,
                points=[point],
            )

            logger.debug(f"Stored embedding for review {review_id} ({product_name})")
            return True

        except Exception as e:
            logger.debug(f"Failed to store embedding for review {review_id}: {e}")
            return False


# Module-level singleton
embedding_service = EmbeddingService()
