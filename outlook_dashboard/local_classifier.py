"""Local scikit-learn classifiers trained from Supabase training_examples.

Trains lightweight TF-IDF + LogisticRegression pipelines for urgency, owner,
and category. Models are persisted as pickle blobs in the local SQLite database
so they survive app restarts without retraining.

USAGE IN triage_email()
  If trained models exist AND the prediction confidence meets the threshold,
  the local classifier result replaces the heuristic — no API call needed.

TRAINING TRIGGER
  POST /api/admin/classifier/train — admin only, explicit trigger.
  Automatically skipped when fewer than MIN_TRAINING_EXAMPLES examples exist.

PRIVACY
  Only redacted body_redacted text is downloaded from Supabase (service role key).
  Raw email bodies are never fetched.
"""
from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import Any

from .runtime_log import get_logger
from .taxonomy import CATEGORIES, DEPARTMENT_OWNERS

_log = get_logger("local_classifier")

MIN_TRAINING_EXAMPLES = 20  # minimum rows before we attempt training
PREDICT_CONFIDENCE_THRESHOLD = 0.70  # min probability to trust local classifier
_MODELS_KEY = "local_classifier_models"


# ── SQLite persistence ────────────────────────────────────────────────────────

def _save_models(models: dict, db_path: Path | None = None) -> None:
    from .database import managed_connect
    blob = pickle.dumps(models, protocol=4)
    with managed_connect(db_path) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS app_kv (
                key TEXT PRIMARY KEY,
                value BLOB NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        from .text_utils import utc_now_iso
        db.execute(
            "INSERT INTO app_kv (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (_MODELS_KEY, blob, utc_now_iso()),
        )


def _load_models(db_path: Path | None = None) -> dict | None:
    try:
        from .database import managed_connect
        with managed_connect(db_path) as db:
            row = db.execute(
                "SELECT value FROM app_kv WHERE key = ?", (_MODELS_KEY,)
            ).fetchone()
        if row:
            return pickle.loads(row[0])  # noqa: S301 — internal, controlled source
    except Exception as exc:
        _log.warning("local_classifier: failed to load models: %s", exc)
    return None


# ── Supabase download ─────────────────────────────────────────────────────────

def _download_training_examples(limit: int = 2000) -> list[dict]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return []
    try:
        import httpx
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        }
        r = httpx.get(
            f"{url}/rest/v1/training_examples",
            params={
                "select": "body_redacted,label_urgency,label_owner,label_category",
                "limit": str(limit),
            },
            headers=headers,
            timeout=15,
        )
        if r.status_code == 200:
            return r.json()
        _log.warning("local_classifier: download failed status=%s", r.status_code)
    except Exception as exc:
        _log.warning("local_classifier: download error: %s", exc)
    return []


# ── Training ──────────────────────────────────────────────────────────────────

def train(db_path: Path | None = None) -> dict:
    """Download training examples from Supabase and train/persist classifiers.

    Returns summary: {trained, examples, targets}.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.feature_extraction.text import TfidfVectorizer

    examples = _download_training_examples()
    n = len(examples)
    if n < MIN_TRAINING_EXAMPLES:
        _log.info("local_classifier: only %s examples, need %s — skipping train", n, MIN_TRAINING_EXAMPLES)
        return {"trained": False, "examples": n, "targets": [], "reason": f"need {MIN_TRAINING_EXAMPLES} examples, have {n}"}

    texts = [str(ex.get("body_redacted") or "") for ex in examples]
    targets_trained = []
    models: dict[str, Any] = {}

    for target, valid_labels in [
        ("urgency", [1, 2, 3, 4, 5]),
        ("owner", DEPARTMENT_OWNERS),
        ("category", CATEGORIES),
    ]:
        key = f"label_{target}"
        y = []
        x_filtered = []
        for text, ex in zip(texts, examples):
            label = ex.get(key)
            if label is None:
                continue
            if target == "urgency":
                try:
                    label = int(label)
                except (ValueError, TypeError):
                    continue
            if label not in valid_labels:
                continue
            y.append(str(label))
            x_filtered.append(text)

        if len(set(y)) < 2 or len(y) < MIN_TRAINING_EXAMPLES:
            _log.info("local_classifier: skipping %s — only %s labeled rows", target, len(y))
            continue

        pipe = Pipeline([
            ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2), sublinear_tf=True)),
            ("clf", LogisticRegression(max_iter=500, C=1.0, class_weight="balanced")),
        ])
        pipe.fit(x_filtered, y)
        models[target] = pipe
        targets_trained.append(target)
        _log.info("local_classifier: trained %s on %s examples classes=%s", target, len(y), list(set(y)))

    if models:
        _save_models(models, db_path=db_path)

    return {"trained": bool(models), "examples": n, "targets": targets_trained}


# ── Prediction ────────────────────────────────────────────────────────────────

_cached_models: dict | None = None
_models_loaded = False


def _get_models(db_path: Path | None = None) -> dict | None:
    global _cached_models, _models_loaded
    if not _models_loaded:
        _cached_models = _load_models(db_path)
        _models_loaded = True
    return _cached_models


def invalidate_cache() -> None:
    global _cached_models, _models_loaded
    _cached_models = None
    _models_loaded = False


def predict(body_text: str, db_path: Path | None = None) -> dict | None:
    """Return classifier predictions if confidence meets threshold, else None.

    Returns dict with urgency, owner, category, confidence_scores, or None if
    models are unavailable or confidence is too low.
    """
    models = _get_models(db_path)
    if not models:
        return None

    result: dict[str, Any] = {"analysis_engine": "local-classifier"}
    confidence_scores: dict[str, float] = {}
    all_confident = True

    for target, model in models.items():
        try:
            proba = model.predict_proba([body_text])[0]
            max_prob = float(max(proba))
            pred = model.classes_[proba.argmax()]
            confidence_scores[target] = round(max_prob, 3)
            if max_prob >= PREDICT_CONFIDENCE_THRESHOLD:
                result[target] = pred
            else:
                all_confident = False
        except Exception as exc:
            _log.warning("local_classifier: predict error target=%s: %s", target, exc)
            all_confident = False

    result["classifier_confidence_scores"] = confidence_scores

    if not all_confident or not any(k in result for k in ("urgency", "owner", "category")):
        return None

    return result
