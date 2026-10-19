"""Okapi BM25 implementation for benchmark text retrieval (AC-113)."""

from __future__ import annotations

import math
import re


def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric tokens."""
    return re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())


class BM25Index:
    """Okapi BM25 scoring model."""

    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.doc_tokens = [tokenize(doc) for doc in corpus]
        self.doc_lengths = [len(doc) for doc in self.doc_tokens]
        self.num_docs = len(corpus)
        self.avg_doc_len = (
            sum(self.doc_lengths) / self.num_docs if self.num_docs > 0 else 0.0
        )

        # Compute document frequencies
        self.df: dict[str, int] = {}
        for doc in self.doc_tokens:
            for term in set(doc):
                self.df[term] = self.df.get(term, 0) + 1

    def idf(self, term: str) -> float:
        """Compute Robertson-Spärck Jones IDF."""
        df_t = self.df.get(term, 0)
        # Using standard smoothed BM25 IDF: ln((N - df + 0.5) / (df + 0.5) + 1)
        return math.log(1.0 + (self.num_docs - df_t + 0.5) / (df_t + 0.5))

    def score(self, query: str, doc_idx: int) -> float:
        """Compute BM25 score between a query and a document by index."""
        q_tokens = tokenize(query)
        if not q_tokens or doc_idx >= len(self.doc_tokens):
            return 0.0

        doc = self.doc_tokens[doc_idx]
        doc_len = self.doc_lengths[doc_idx]
        if self.avg_doc_len == 0:
            return 0.0

        # Term frequencies in document
        tf_map: dict[str, int] = {}
        for t in doc:
            tf_map[t] = tf_map.get(t, 0) + 1

        score = 0.0
        for term in q_tokens:
            tf = tf_map.get(term, 0)
            if tf > 0:
                term_idf = self.idf(term)
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (
                    1.0 - self.b + self.b * (doc_len / self.avg_doc_len)
                )
                score += term_idf * (numerator / denominator)

        return score

    def rank(self, query: str) -> list[tuple[int, float]]:
        """Rank all documents in corpus for a query, returning list of (doc_index, score) sorted descending."""
        scored = [(i, self.score(query, i)) for i in range(self.num_docs)]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
