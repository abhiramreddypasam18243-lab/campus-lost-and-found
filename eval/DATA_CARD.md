# DATA_CARD.md: Benchmark Dataset Card

## 1. Dataset Summary
The benchmark dataset for the Smart Campus Lost-and-Found Network is designed to evaluate retrieval performance across multimodal, temporal, and spatial signals without compromising student privacy.

* **Total items:** 300 ground-truth pairs (lost report + found report) + 100 background found reports (unclaimed items).
* **Categories:** 12 fixed categories (`bottle`, `bag`, `wallet`, `phone`, `laptop_tablet`, `earphones`, `keys`, `id_card`, `clothing`, `book`, `accessory`, `other`).
* **Splits:**
  * 30% Development Set (90 items) — used exclusively for hyperparameter grid tuning and learned fusion training.
  * 70% Test Set (210 items) — frozen and evaluated exactly once using the frozen configuration.
* **Consented Subsets:**
  * Real-photo subset: 60 items with 2 distinct photos each taken under varying lighting, angles, and backgrounds.
  * Human-written text subset: 60 items written independently and blind by two contributors.

## 2. Privacy and Ethics
* **No Real Student Data:** Zero production or actual student lost/found reports are included.
* **No Faces or Identifiable Features:** Photos are screened to ensure zero human faces, license plates, ID card numbers, or personally identifiable information (PII).
* **EXIF Stripping:** All image metadata, including GPS coordinates and camera serial numbers, is stripped during preprocessing.
* **Consent:** Written consent from contributors of the 60-item photo subset is archived.
