"""Embedding service for storing review content in Qdrant vector database."""

import asyncio
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Vector dimensions per provider
_VECTOR_DIMS = {
    "gemini": 768,   # text-embedding-004
    "openai": 1536,  # text-embedding-3-small
}


class EmbeddingService:
    """
    Generates embeddings and stores them in Qdrant.

    Supports both Gemini (text-embedding-004) and OpenAI (text-embedding-3-small).
    Gracefully degrades if Qdrant or the embedding API is unavailable —
    review ingestion will still succeed, just without vector search capability.
    """

    def __init__(self):
        self._qdrant = None
        self._provider: Optional[str] = None
        self._genai = None
        self._openai_client = None
        self._embedding_model: Optional[str] = None
        self._vector_size: int = 768

    async def initialize(self) -> None:
        """Connect to Qdrant and initialize the embedding provider."""
        try:
            # Determine provider
            provider = settings.LLM_PROVIDER.lower()

            if provider == "openai" and settings.OPENAI_API_KEY:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                self._embedding_model = settings.OPENAI_EMBEDDING_MODEL
                self._vector_size = _VECTOR_DIMS.get("openai", 1536)
                self._provider = "openai"
            elif settings.GEMINI_API_KEY:
                import google.generativeai as genai
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self._genai = genai
                self._embedding_model = settings.EMBEDDING_MODEL
                self._vector_size = _VECTOR_DIMS.get("gemini", 768)
                self._provider = "gemini"
            else:
                logger.warning("No embedding provider available (no API key set)")
                return

            # Connect to Qdrant
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            self._qdrant = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                timeout=10,
            )

            # Ensure collection exists
            collections = await asyncio.to_thread(
                self._qdrant.get_collections
            )
            collection_names = [c.name for c in collections.collections]

            if settings.QDRANT_COLLECTION not in collection_names:
                await asyncio.to_thread(
                    self._qdrant.create_collection,
                    collection_name=settings.QDRANT_COLLECTION,
                    vectors_config=VectorParams(
                        size=self._vector_size,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info(
                    f"Created Qdrant collection: {settings.QDRANT_COLLECTION} "
                    f"(dims={self._vector_size})"
                )

            logger.info(
                f"Embedding service initialized "
                f"({self._provider} / {self._embedding_model}, Qdrant)"
            )

        except Exception as e:
            logger.warning(f"Embedding service unavailable — vector search disabled: {e}")
            self._qdrant = None
            self._provider = None

    @property
    def is_available(self) -> bool:
        return self._provider is not None

    async def generate_embedding(self, text: str) -> Optional[list]:
        """Generate an embedding vector for the given text."""
        if not self._provider:
            return None
        try:
            truncated = text[:8000] if len(text) > 8000 else text

            if self._provider == "openai":
                result = await asyncio.to_thread(
                    self._openai_client.embeddings.create,
                    model=self._embedding_model,
                    input=truncated,
                )
                return result.data[0].embedding

            else:  # gemini
                result = await asyncio.to_thread(
                    self._genai.embed_content,
                    model=self._embedding_model,
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
        if not self._qdrant or not self._provider:
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
