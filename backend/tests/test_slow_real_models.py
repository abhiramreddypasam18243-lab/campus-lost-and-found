"""Real-model integration (spec 18: marked slow). Run inside the backend image: pytest -m slow.

Expected orderings, not exact values: paraphrases of the same item must be closer than
different items, and CLIP must pair each colour photo with its own caption.
"""

from pathlib import Path

import pytest
from PIL import Image

from app.core.config import get_settings
from app.services.embedder import CLIP_DIMENSION, TEXT_DIMENSION, ModelEmbedder

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def embedder() -> ModelEmbedder:
    pytest.importorskip("sentence_transformers")
    settings = get_settings()
    return ModelEmbedder(settings.MODEL_DIR, settings.TEXT_MODEL_NAME, settings.CLIP_MODEL_NAME)


def _cos(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_ac_51_real_text_embeddings_rank_paraphrase_first(embedder: ModelEmbedder) -> None:
    flask = embedder.embed_text("bottle Lost navy flask Dark blue insulated flask, dented base")
    bottle = embedder.embed_text("bottle Found dark blue water bottle Metal bottle on a desk")
    charger = embedder.embed_text("laptop_tablet Black laptop charger USB-C power adapter")
    assert len(flask) == TEXT_DIMENSION
    assert _cos(flask, flask) == pytest.approx(1.0, abs=1e-5)  # L2-normalised (6.1)
    assert _cos(flask, bottle) > _cos(flask, charger)


def test_ac_55_real_clip_pairs_photo_with_caption(embedder: ModelEmbedder, tmp_path: Path) -> None:
    blue, red = tmp_path / "blue.png", tmp_path / "red.png"
    Image.new("RGB", (224, 224), (20, 40, 200)).save(blue)
    Image.new("RGB", (224, 224), (210, 30, 30)).save(red)
    v_blue, v_red = embedder.embed_image(blue), embedder.embed_image(red)
    t_blue = embedder.embed_clip_text("a plain blue square")
    t_red = embedder.embed_clip_text("a plain red square")
    assert len(v_blue) == CLIP_DIMENSION
    assert _cos(v_blue, t_blue) > _cos(v_blue, t_red)
    assert _cos(v_red, t_red) > _cos(v_red, t_blue)


def test_clip_text_accepts_descriptions_beyond_77_tokens(embedder: ModelEmbedder) -> None:
    """Descriptions may be 2,000 characters; CLIP's text encoder takes 77 tokens."""
    vector = embedder.embed_clip_text("blue bottle with stickers " * 80)
    assert len(vector) == CLIP_DIMENSION
