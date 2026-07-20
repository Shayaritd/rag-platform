"""
Embedding provider abstraction. Local sentence-transformers is the default
so ingestion/query never costs API credits; Gemini embeddings are an
opt-in path if higher quality is worth the cost.
"""
from functools import lru_cache
from app.core.config import get_settings

settings = get_settings()


class LocalEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, normalize_embeddings=True).tolist()


class GeminiEmbedder:
    def __init__(self, api_key: str):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._genai = genai

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            self._genai.embed_content(model="models/text-embedding-004", content=t)["embedding"]
            for t in texts
        ]


@lru_cache
def get_embedder():
    if settings.EMBEDDING_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
        return GeminiEmbedder(settings.GEMINI_API_KEY)
    return LocalEmbedder(settings.EMBEDDING_MODEL)
