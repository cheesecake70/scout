"""Text embeddings. Uses sentence-transformers when installed; otherwise a hashed bag-of-words fallback
so the pipeline still runs (worse ranking, but runs) on machines without torch."""
from __future__ import annotations

import hashlib
import itertools
import logging
import re

import numpy as np

log = logging.getLogger(__name__)
_model = None
_model_name = None
DIM_FALLBACK = 512


def _load(model_name: str):
    global _model, _model_name
    if _model is not None and _model_name == model_name:
        return _model
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        _model = SentenceTransformer(model_name, device="cpu")
        _model_name = model_name
        log.info("embedding model: %s", model_name)
    except Exception as e:  # noqa: BLE001
        log.warning("sentence-transformers unavailable (%s); using hashed fallback embeddings", e)
        _model = False
        _model_name = model_name
    return _model


_tok = re.compile(r"[a-z][a-z0-9\-]{2,}")


def _hash_embed(texts: list[str]) -> np.ndarray:
    out = np.zeros((len(texts), DIM_FALLBACK), dtype=np.float32)
    for i, t in enumerate(texts):
        toks = _tok.findall(t.lower())
        grams = toks + [f"{a}_{b}" for a, b in itertools.pairwise(toks)]
        for g in grams:
            h = int(hashlib.blake2b(g.encode(), digest_size=8).hexdigest(), 16)
            out[i, h % DIM_FALLBACK] += 1.0 if (h >> 63) else -1.0
        n = np.linalg.norm(out[i])
        if n:
            out[i] /= n
    return out


def embed(texts: list[str], model_name: str) -> np.ndarray:
    if not texts:
        return np.zeros((0, DIM_FALLBACK), dtype=np.float32)
    m = _load(model_name)
    if m:
        v = m.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
        return np.asarray(v, dtype=np.float32)
    return _hash_embed(texts)


def cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Row-wise cosine between (n,d) and (d,) or (m,d). Inputs assumed unit-normalised."""
    return a @ b.T if b.ndim == 2 else a @ b


def unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n else v
