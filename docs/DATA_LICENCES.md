# DATA_LICENCES.md: Data and Model Licences

This document records the licences, origins, and permissions for all datasets, model weights, synthetic data, and photos used within the **Smart Campus Lost-and-Found Network**, in full compliance with **AC-148** and project ethics guidelines.

---

## 1. Machine Learning Models and Pretrained Weights

| Component | Model Name / Identifier | Source Repository / Provider | Licence | Intended Use & Modifications |
| :--- | :--- | :--- | :--- | :--- |
| **Text Embedding Model** | `all-MiniLM-L6-v2` | [HuggingFace / sentence-transformers](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | **Apache 2.0** | Semantic embedding of lost & found titles and descriptions (384-dimensional dense vectors). Offline inference only. |
| **Vision-Text Model** | `clip-ViT-B-32` | [OpenAI / HuggingFace](https://huggingface.co/openai/clip-vit-base-patch32) | **MIT Licence** | Zero-shot visual representation and cross-modal embedding of item photographs (512-dimensional dense vectors). Offline inference only. |

Both models are baked into container images or cached locally, requiring zero network egress during runtime execution (**AC-139**).

---

## 2. Evaluation Datasets

| Dataset / Asset | Origin / Author | Volume | Licence | Consent & Privacy Compliance |
| :--- | :--- | :--- | :--- | :--- |
| **Synthetic Campus Benchmark** | Procedural Seeded Generator (`eval/generator.py`) | 300 ground-truth pairs + 100 unclaimed background items | **CC0 1.0 (Public Domain)** | Completely synthetic. Contains zero real student records, PII, or actual university reports. |
| **Consented Real-Photo Subset** | Consenting University Contributors | 60 items (2 photos each = 120 images) | **CC-BY 4.0** | Donated under written consent for academic research. All EXIF metadata (GPS, device identifiers) stripped. No human faces, IDs, or vehicle plates. |
| **Consented Independent Text Descriptions** | University Contributors (Blind Pairs) | 60 pairs | **CC-BY 4.0** | Blind descriptions authored independently without access to paired counterpart text. |

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
