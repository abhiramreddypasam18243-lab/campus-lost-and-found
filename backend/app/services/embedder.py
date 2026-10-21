"""Embedding backends (spec 6.1).

`ModelEmbedder` runs the pinned models baked into the image (D4): all-MiniLM-L6-v2 for the
text signal and CLIP ViT-B/32 for image vectors and the cross-modal (text-to-image) signal.
`StandinEmbedder` returns deterministic hash vectors so the fast test suite needs no models.
Only the worker calls `embed_*`; web requests never compute embeddings (D7).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

from app.core.config import get_settings
from app.services.embeddings import (
    generate_standin_image_embedding,
    generate_standin_text_embedding,
)

TEXT_DIMENSION = 384
CLIP_DIMENSION = 512

# CLIP's text encoder accepts at most 77 tokens. Report descriptions run up to 2,000
# characters, so the cross-modal text is cut to its first words before tokenising.
CLIP_MAX_WORDS = 40


def clip_text_input(text: str) -> str:
    return " ".join(text.split()[:CLIP_MAX_WORDS])


class Embedder(Protocol):
    def embed_text(self, text: str) -> list[float]:
        """Sentence embedding (384-d, L2-normalised) for the text signal."""
        ...

    def embed_clip_text(self, text: str) -> list[float]:
        """CLIP text embedding (512-d, L2-normalised) in the same space as image vectors."""
        ...

    def embed_image(self, path: Path) -> list[float]:
        """CLIP image embedding (512-d, L2-normalised)."""
        ...


class StandinEmbedder:
    def embed_text(self, text: str) -> list[float]:
        return generate_standin_text_embedding(text, dimension=TEXT_DIMENSION)

    def embed_clip_text(self, text: str) -> list[float]:
        return generate_standin_image_embedding(
            "clip-text:" + clip_text_input(text), dimension=CLIP_DIMENSION
        )

    def embed_image(self, path: Path) -> list[float]:
        return generate_standin_image_embedding(
            "image:" + path.read_bytes().hex(), dimension=CLIP_DIMENSION
        )


class ModelEmbedder:
    def __init__(self, model_dir: str, text_model: str, clip_model: str) -> None:
        # Imported lazily: the API process and the test suite never load torch.
        from sentence_transformers import SentenceTransformer

        root = Path(model_dir)
        self._text: Any = SentenceTransformer(str(root / text_model), device="cpu")
        self._clip: Any = SentenceTransformer(str(root / clip_model), device="cpu")

    @staticmethod
    def _as_list(vector: Any) -> list[float]:
        return [float(x) for x in vector.tolist()]

    def embed_text(self, text: str) -> list[float]:
        return self._as_list(self._text.encode(text, normalize_embeddings=True))

    def embed_clip_text(self, text: str) -> list[float]:
        return self._as_list(self._clip.encode(clip_text_input(text), normalize_embeddings=True))

    def embed_image(self, path: Path) -> list[float]:
        with Image.open(path) as img:
            rgb = img.convert("RGB")
        return self._as_list(self._clip.encode(rgb, normalize_embeddings=True))


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.EMBEDDING_BACKEND == "model":
        return ModelEmbedder(settings.MODEL_DIR, settings.TEXT_MODEL_NAME, settings.CLIP_MODEL_NAME)
    return StandinEmbedder()
