# DATA_LICENCES.md: Data and Model Licences

This document records the licences, origins, and permissions for all datasets, model weights, synthetic data, and photos used within the **Smart Campus Lost-and-Found Network**, in full compliance with **AC-148** and project ethics guidelines.

---

## 1. Machine Learning Models and Pretrained Weights

| Component | Model Name / Identifier | Source Repository / Provider | Licence | Intended Use & Modifications |
| :--- | :--- | :--- | :--- | :--- |
| **Text Embedding Model** | `all-MiniLM-L6-v2` | [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | **Apache 2.0** | Semantic embedding of lost & found titles and descriptions (384-dimensional dense vectors). Offline inference only. |
| **Vision-Text Model** | `clip-ViT-B-32` | [sentence-transformers/clip-ViT-B-32](https://huggingface.co/sentence-transformers/clip-ViT-B-32) (wrapper of OpenAI CLIP ViT-B/32) | **MIT Licence** (OpenAI CLIP) | Image vectors and cross-modal text vectors in one 512-dimensional space. Offline inference only. |

**Pinned revisions and checksums** (source of truth: `backend/models.lock.json`; the Docker build fails on any mismatch):

| Model | Hugging Face revision | Verified file | SHA-256 |
| :--- | :--- | :--- | :--- |
| `all-MiniLM-L6-v2` | `1110a243fdf4706b3f48f1d95db1a4f5529b4d41` | `model.safetensors` | `53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db` |
| `clip-ViT-B-32` | `327ab6726d33c0e22f920c83f2ff9e4bd38ca37f` | `0_CLIPModel/model.safetensors` | `99d28a652e6ec46629ab7047a0ac82c69b1fe11e0ce672c43af65d3a9a3fc05d` |

Both models are downloaded once during `docker build` by `backend/scripts/fetch_models.py` into `/models` and baked into the backend/worker image. Containers run with `HF_HUB_OFFLINE=1`, so no model download happens at runtime (**AC-139**). The fast test suite uses deterministic stand-in vectors (`EMBEDDING_BACKEND=standin`) and never loads the models.

---

## 2. Evaluation Datasets

| Dataset / Asset | Origin / Author | Volume | Licence | Consent & Privacy Compliance |
| :--- | :--- | :--- | :--- | :--- |
| **Synthetic Campus Benchmark** | Procedural Seeded Generator (`eval/generator.py`) | 300 ground-truth pairs + 100 unclaimed background items | **CC0 1.0 (Public Domain)** | Completely synthetic. Contains zero real student records, PII, or actual university reports. |
| **Real-photo subset** | — | **Not collected** | — | No photos exist. Before any are used: written consent per contributor, a licence per photo, face/ID/plate screening and EXIF removal must be recorded here. |
| **Human-written text subset** | — | **Not collected** | — | All benchmark text is template-generated. |

---

## 3. Campus Geospatial & Adjacency Graph

| Component | Description | Licence | Privacy Note |
| :--- | :--- | :--- | :--- |
| **Campus Location Tree** | Fictionalized campus hierarchy (`campus` -> `building` -> `floor` -> `room`/`area`) | **CC0 1.0** | Synthetically defined node hierarchy for evaluation and demonstration. |
| **Building Adjacency Graph** | Symmetrical walking proximity edges (`LocationAdjacency`) | **CC0 1.0** | Coordinate approximations centered on representative latitude/longitude coordinates. |

---

## 4. Software Dependencies and Tooling

All third-party runtime libraries are tracked with exact pinned versions:
* **FastAPI**: MIT Licence
* **SQLAlchemy & Asyncpg**: MIT / Apache 2.0
* **pgvector**: PostgreSQL Licence
* **React & Vite**: MIT Licence
* **Pytest & Ruff**: MIT / Apache 2.0
