"""Local scikit-learn classifiers trained from Supabase training_examples.

Trains TF-IDF + LogisticRegression pipelines for urgency, owner, and category.
Subject tokens are used as a separate high-weight feature channel.
Models are versioned and persisted as pickle blobs in SQLite.

Enhancements over the original:
- Subject tokens joined with body as a weighted combined input
- Cross-validation accuracy reported per target during training
- Feature importance (top TF-IDF terms) extracted per class
- Per-category confidence thresholds (rare categories get lower thresholds)
- Model versioning: each trained model bundle is stamped with a version ID
  and training timestamp; previous version retained for rollback
- Calibrated probabilities via CalibratedClassifierCV (Platt scaling)
- Label distribution logged to detect imbalance
"""
from __future__ import annotations

import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import get_settings
from .runtime_log import get_logger
from .taxonomy import CATEGORIES, DEPARTMENT_OWNERS

_log = get_logger("local_classifier")

MIN_TRAINING_EXAMPLES = 20
_MODELS_KEY = "local_classifier_models"
_MODELS_KEY_PREV = "local_classifier_models_prev"
_META_KEY = "local_classifier_meta"
_META_KEY_PREV = "local_classifier_meta_prev"

# Per-target default confidence thresholds.
# Rare categories like "Accessibility request" need a lower threshold or they
# are never predicted; common ones like "Internal request" can stay high.
_DEFAULT_CONFIDENCE_THRESHOLD = 0.60
_TARGET_THRESHOLDS: dict[str, float] = {
    "urgency": 0.62,
    "owner": 0.58,
    "category": 0.55,
}
# Per-class override: if any class in the prediction set gets this label,
# apply the class-specific minimum probability instead of the target default.
_CLASS_THRESHOLDS: dict[str, float] = {
    "Accessibility request": 0.40,
    "Billing dispute": 0.45,
    "Urgent same-day arrival": 0.45,
    "Complaint": 0.48,
    "Duplicate follow-up": 0.40,
}


# ── SQLite persistence ────────────────────────────────────────────────────────

def _save_models(models: dict, meta: dict, db_path: Path | None = None) -> None:
    from .database import managed_connect
    from .text_utils import utc_now_iso
    blob = pickle.dumps(models, protocol=4)
    meta_blob = pickle.dumps(meta, protocol=4)
    with managed_connect(db_path) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS app_kv (
                key TEXT PRIMARY KEY, value BLOB NOT NULL, updated_at TEXT NOT NULL
            )"""
        )
        now = utc_now_iso()
        # Rotate current → prev before overwriting (only if a current model exists)
        existing = db.execute("SELECT value FROM app_kv WHERE key = ?", (_MODELS_KEY,)).fetchone()
        if existing:
            db.execute(
                "INSERT INTO app_kv (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (_MODELS_KEY_PREV, existing[0], now),
            )
        existing_meta = db.execute("SELECT value FROM app_kv WHERE key = ?", (_META_KEY,)).fetchone()
        if existing_meta:
            db.execute(
                "INSERT INTO app_kv (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (_META_KEY_PREV, existing_meta[0], now),
            )
        for key, value in [(_MODELS_KEY, blob), (_META_KEY, meta_blob)]:
            db.execute(
                "INSERT INTO app_kv (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, value, now),
            )


def _load_models(db_path: Path | None = None) -> tuple[dict | None, dict]:
    try:
        from .database import managed_connect
        with managed_connect(db_path) as db:
            model_row = db.execute("SELECT value FROM app_kv WHERE key = ?", (_MODELS_KEY,)).fetchone()
            meta_row = db.execute("SELECT value FROM app_kv WHERE key = ?", (_META_KEY,)).fetchone()
        models = pickle.loads(model_row[0]) if model_row and model_row[0] else None  # noqa: S301
        meta = pickle.loads(meta_row[0]) if meta_row and meta_row[0] else {}  # noqa: S301
        return models, meta
    except Exception as exc:
        _log.warning("local_classifier: failed to load models: %s", exc)
    return None, {}


# ── Supabase download ─────────────────────────────────────────────────────────

def _download_training_examples(limit: int = 5000) -> list[dict]:
    url = get_settings().supabase_url.rstrip("/")
    key = get_settings().supabase_service_role_key
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
                "select": "subject_tokens,body_redacted,label_urgency,label_owner,label_category,labeling_engine",
                "human_reviewed": "eq.true",
                "order": "created_at.asc",
                "limit": str(limit),
            },
            headers=headers,
            timeout=20,
        )
        if r.status_code == 200:
            return r.json()
        _log.warning("local_classifier: download status=%s", r.status_code)
    except Exception as exc:
        _log.warning("local_classifier: download error: %s", exc)
    return []


def _load_local_examples(db_path=None, limit: int = 5000) -> list[dict]:
    """Load training examples from local triage_feedback + bootstrap seed data.

    Returns zero examples rather than raising.
    """
    results: list[dict] = []
    try:
        from .database import get_local_training_examples
        results.extend(get_local_training_examples(limit=limit, db_path=db_path))
    except Exception as exc:
        _log.warning("local_classifier: feedback example load error: %s", exc)
    try:
        from .training_bootstrap_data import get_bootstrap_examples
        results.extend(get_bootstrap_examples(db_path=db_path))
    except Exception as exc:
        _log.warning("local_classifier: bootstrap example load error: %s", exc)
    return results


def _merge_examples(supabase: list[dict], local: list[dict]) -> list[dict]:
    """Merge Supabase and local feedback examples, deduplicating by subject+body fingerprint."""
    seen: set[str] = set()
    merged: list[dict] = []
    for ex in supabase + local:
        key = f"{ex.get('subject_tokens', '')}|{ex.get('body_redacted', '')[:120]}"
        if key not in seen:
            seen.add(key)
            merged.append(ex)
    return merged


def _make_input_text(example: dict) -> str:
    """Combine subject tokens + body with subject weighted 3x."""
    subject = str(example.get("subject_tokens") or "")
    body = str(example.get("body_redacted") or "")
    # Repeat subject tokens 3 times to give them more TF-IDF weight
    return f"{subject} {subject} {subject} {body}".strip()


# ── Cross-validation ──────────────────────────────────────────────────────────

def _cross_val_accuracy(pipe, X: list[str], y: list[str], cv: int = 3) -> float:
    try:
        from sklearn.model_selection import cross_val_score
        if len(X) < cv * 5:
            return -1.0
        scores = cross_val_score(pipe, X, y, cv=cv, scoring="accuracy", n_jobs=1)
        return round(float(scores.mean()), 4)
    except Exception:
        return -1.0


# ── Feature importance ────────────────────────────────────────────────────────

def _top_features(pipe, n: int = 15) -> dict[str, list[str]]:
    """Return top TF-IDF terms per class from the fitted pipeline."""
    try:
        from sklearn.pipeline import Pipeline
        vectorizer = pipe.named_steps.get("tfidf")
        clf = pipe.named_steps.get("clf")
        if vectorizer is None or clf is None:
            return {}
        feature_names = vectorizer.get_feature_names_out()
        result: dict[str, list[str]] = {}
        # LogisticRegression: coef_ shape = (n_classes, n_features)
        # CalibratedClassifierCV: access base_estimator
        estimator = clf
        if hasattr(clf, "estimator"):
            estimator = clf.estimator
        if not hasattr(estimator, "coef_"):
            return {}
        classes = list(estimator.classes_)
        for i, cls in enumerate(classes):
            top_idx = estimator.coef_[i].argsort()[-n:][::-1]
            result[str(cls)] = [str(feature_names[j]) for j in top_idx]
        return result
    except Exception:
        return {}


# ── Training ──────────────────────────────────────────────────────────────────

def train(db_path: Path | None = None) -> dict:
    """Download human-reviewed training examples and train/persist classifiers.

    Falls back to local triage_feedback corrections when Supabase has fewer
    than MIN_TRAINING_EXAMPLES. Merges both sources, deduplicating by content.

    Returns a detailed summary dict with accuracy metrics, label distributions,
    and feature importance snippets per target.
    """
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    supabase_examples = _download_training_examples()
    local_examples = _load_local_examples(db_path=db_path)
    examples = _merge_examples(supabase_examples, local_examples)
    _log.info(
        "local_classifier: %s supabase + %s local = %s merged examples",
        len(supabase_examples), len(local_examples), len(examples),
    )
    n = len(examples)
    if n < MIN_TRAINING_EXAMPLES:
        _log.info("local_classifier: only %s examples, need %s — skipping", n, MIN_TRAINING_EXAMPLES)
        return {
            "trained": False, "examples": n, "targets": [],
            "reason": f"need {MIN_TRAINING_EXAMPLES} human-reviewed examples, have {n}",
        }

    all_texts = [_make_input_text(ex) for ex in examples]
    targets_trained: list[str] = []
    models: dict[str, Any] = {}
    target_meta: dict[str, Any] = {}

    for target, valid_labels in [
        ("urgency", [1, 2, 3, 4, 5]),
        ("owner", list(DEPARTMENT_OWNERS)),
        ("category", list(CATEGORIES)),
    ]:
        db_key = f"label_{target}"
        y: list[str] = []
        x_filtered: list[str] = []
        for text, ex in zip(all_texts, examples):
            label = ex.get(db_key)
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
            _log.info("local_classifier: skipping %s — %s labeled rows, %s classes", target, len(y), len(set(y)))
            continue

        # Log label distribution
        from collections import Counter
        dist = dict(Counter(y).most_common())

        # Base pipeline — CalibratedClassifierCV for better probability estimates
        base_lr = LogisticRegression(max_iter=600, C=1.0, class_weight="balanced", solver="lbfgs")
        from collections import Counter as _Counter
        min_class_size = min(_Counter(y).values())
        cv_count = min(5, max(2, len(y) // 20))
        # cv must not exceed the smallest class size; skip calibration when only 1 example/class
        cv_count = min(cv_count, min_class_size)
        use_calibration = cv_count >= 2
        clf = CalibratedClassifierCV(base_lr, method="sigmoid", cv=cv_count) if use_calibration else base_lr

        # min_df=1 when dataset is small so no tokens are discarded
        min_df = 2 if len(x_filtered) >= 50 else 1
        pipe = Pipeline([
            ("tfidf", TfidfVectorizer(
                max_features=8000,
                ngram_range=(1, 3),
                sublinear_tf=True,
                min_df=min_df,
                strip_accents="unicode",
            )),
            ("clf", clf),
        ])
        pipe.fit(x_filtered, y)

        cv_acc = _cross_val_accuracy(
            Pipeline([
                ("tfidf", TfidfVectorizer(max_features=8000, ngram_range=(1, 3), sublinear_tf=True, min_df=2)),
                ("clf", LogisticRegression(max_iter=600, C=1.0, class_weight="balanced")),
            ]),
            x_filtered, y, cv=min(3, cv_count),
        )
        top_feats = _top_features(pipe)

        models[target] = pipe
        targets_trained.append(target)
        target_meta[target] = {
            "examples": len(y),
            "classes": len(set(y)),
            "label_distribution": dist,
            "cv_accuracy": cv_acc,
            "top_features": top_feats,
        }
        _log.info(
            "local_classifier: trained %s on %s examples, cv_acc=%.3f, classes=%s",
            target, len(y), cv_acc if cv_acc >= 0 else -1, len(set(y)),
        )

    version_id = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    meta = {
        "version_id": version_id,
        "trained_at": datetime.now(tz=timezone.utc).isoformat(),
        "total_examples_downloaded": n,
        "examples_supabase": len(supabase_examples),
        "examples_local": len(local_examples),
        "targets": target_meta,
    }

    if models:
        _save_models(models, meta, db_path=db_path)
        invalidate_cache()

    return {
        "trained": bool(models),
        "version_id": version_id,
        "examples": n,
        "examples_supabase": len(supabase_examples),
        "examples_local": len(local_examples),
        "targets": targets_trained,
        "accuracy": {t: target_meta[t].get("cv_accuracy") for t in targets_trained},
        "label_distributions": {t: target_meta[t].get("label_distribution") for t in targets_trained},
        "feature_importance": {t: target_meta[t].get("top_features") for t in targets_trained},
    }


# ── Prediction ────────────────────────────────────────────────────────────────

_cached_models: dict | None = None
_cached_meta: dict = {}
_models_loaded = False


def _get_models(db_path: Path | None = None) -> tuple[dict | None, dict]:
    global _cached_models, _cached_meta, _models_loaded
    if not _models_loaded:
        _cached_models, _cached_meta = _load_models(db_path)
        _models_loaded = True
    return _cached_models, _cached_meta


def invalidate_cache() -> None:
    global _cached_models, _cached_meta, _models_loaded
    _cached_models = None
    _cached_meta = {}
    _models_loaded = False


def get_model_meta(db_path: Path | None = None) -> dict:
    """Return metadata about the currently loaded model bundle."""
    _, meta = _get_models(db_path)
    return meta


def get_classifier_status(db_path: Path | None = None) -> dict:
    """Return a rich admin-facing status snapshot for the local classifier.

    Includes training state, per-target accuracy, label distribution, example
    counts, stale/no-model warnings, and rollback availability.
    """
    models, meta = _get_models(db_path)
    has_model = bool(models and meta.get("version_id"))

    def _table_exists(db: Any, table_name: str) -> bool:
        row = db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None

    def _count_rows(db: Any, table_name: str, where_clause: str = "") -> int:
        if not _table_exists(db, table_name):
            return 0
        query = f"SELECT COUNT(*) FROM {table_name}"  # noqa: S608 - trusted internal table names
        if where_clause:
            query += f" WHERE {where_clause}"
        row = db.execute(query).fetchone()
        return int(row[0]) if row else 0

    has_prev = False
    local_count = 0
    bootstrap_count = 0
    feedback_count = 0
    try:
        from .database import managed_connect
        with managed_connect(db_path) as db:
            prev_model = db.execute(
                "SELECT value FROM app_kv WHERE key = ?", (_MODELS_KEY_PREV,)
            ).fetchone()
            prev_meta = db.execute(
                "SELECT value FROM app_kv WHERE key = ?", (_META_KEY_PREV,)
            ).fetchone()
            has_prev = bool(prev_model and prev_model[0] and prev_meta and prev_meta[0])
            bootstrap_count = _count_rows(
                db,
                "training_bootstrap",
                "label_urgency IS NOT NULL",
            )
            feedback_count = _count_rows(
                db,
                "triage_feedback",
                "corrected_urgency IS NOT NULL",
            )
            local_count = bootstrap_count + feedback_count
    except Exception as exc:
        _log.debug("local_classifier: failed to collect status counts: %s", exc)

    targets_meta = meta.get("targets") or {}
    target_summaries: dict[str, dict] = {}
    for target, tmeta in targets_meta.items():
        cv = tmeta.get("cv_accuracy", -1.0)
        target_summaries[target] = {
            "examples": tmeta.get("examples", 0),
            "classes": tmeta.get("classes", 0),
            "cv_accuracy": cv,
            "cv_status": (
                "ok" if cv >= 0.5
                else "low" if cv >= 0
                else "insufficient_data"
            ),
            "label_distribution": tmeta.get("label_distribution") or {},
        }

    warnings: list[str] = []
    if not has_model:
        warnings.append("No trained model available — classifier predictions are disabled")
    else:
        trained_at = meta.get("trained_at", "")
        if trained_at:
            from datetime import datetime, timezone
            try:
                age_days = (
                    datetime.now(tz=timezone.utc)
                    - datetime.fromisoformat(trained_at)
                ).days
                if age_days > 30:
                    warnings.append(f"Model is {age_days} days old — consider retraining")
            except Exception:
                pass
        for target, tsummary in target_summaries.items():
            if tsummary["cv_status"] == "low":
                warnings.append(
                    f"Target '{target}' CV accuracy {tsummary['cv_accuracy']:.0%} is low — "
                    "add more reviewed training examples to improve"
                )
            elif tsummary["cv_status"] == "insufficient_data":
                warnings.append(
                    f"Target '{target}' had insufficient data for cross-validation"
                )

    sources: list[str] = []
    examples_supabase = int(meta.get("examples_supabase", 0) or 0)
    examples_local = int(meta.get("examples_local", local_count) or 0)
    total_at_train = int(meta.get("total_examples_downloaded", 0) or 0)
    available_examples = max(local_count + examples_supabase, total_at_train)
    if examples_supabase > 0:
        sources.append("supabase")
    if feedback_count > 0 or examples_local > 0:
        sources.append("local_feedback")
    if bootstrap_count > 0:
        sources.append("bootstrap")
    if not sources and has_model:
        sources.append("bootstrap")

    return {
        "has_model": has_model,
        "version_id": meta.get("version_id", ""),
        "trained_at": meta.get("trained_at", ""),
        "total_examples_at_train_time": total_at_train,
        "examples_supabase": examples_supabase,
        "examples_local": examples_local,
        "available_training_examples": available_examples,
        "human_reviewed_count": examples_supabase,
        "local_examples_count": local_count,
        "targets_trained": sorted(targets_meta.keys()),
        "targets": target_summaries,
        "data_sources": sources,
        "rollback_available": has_prev,
        "warnings": warnings,
        "needs_training": (
            not has_model
            or (available_examples > (total_at_train * 1.5) if total_at_train else False)
        ),
    }


def rollback_model(db_path: Path | None = None) -> dict:
    """Restore the previous model bundle from SQLite (if available).

    Returns {"rolled_back": bool, "version_id": str, "reason": str}.
    """
    try:
        from .database import managed_connect
        from .text_utils import utc_now_iso
        with managed_connect(db_path) as db:
            prev_row = db.execute(
                "SELECT value FROM app_kv WHERE key = ?", (_MODELS_KEY_PREV,)
            ).fetchone()
            prev_meta_row = db.execute(
                "SELECT value FROM app_kv WHERE key = ?", (_META_KEY_PREV,)
            ).fetchone()
            if not prev_row or not prev_row[0]:
                return {"rolled_back": False, "version_id": "", "reason": "No previous model available"}
            if not prev_meta_row or not prev_meta_row[0]:
                return {
                    "rolled_back": False,
                    "version_id": "",
                    "reason": "Previous model metadata is missing",
                }
            # Restore previous model and metadata together.
            now = utc_now_iso()
            for key, value in ((_MODELS_KEY, prev_row[0]), (_META_KEY, prev_meta_row[0])):
                db.execute(
                    "INSERT INTO app_kv (key, value, updated_at) VALUES (?, ?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                    (key, value, now),
                )
        # Clear the in-memory cache so the restored model is loaded next predict()
        invalidate_cache()
        models, meta = _get_models(db_path)
        return {
            "rolled_back": True,
            "version_id": meta.get("version_id", "unknown"),
            "reason": "Restored previous model bundle",
        }
    except Exception as exc:
        return {"rolled_back": False, "version_id": "", "reason": str(exc)[:200]}


def feature_importance(db_path: Path | None = None) -> dict[str, dict[str, list[str]]]:
    """Return top features per class for each trained target."""
    _, meta = _get_models(db_path)
    result: dict[str, dict[str, list[str]]] = {}
    for target, tmeta in (meta.get("targets") or {}).items():
        fi = tmeta.get("top_features")
        if fi:
            result[target] = fi
    return result


def predict(body_text: str, subject_tokens: str = "", db_path: Path | None = None) -> dict | None:
    """Return classifier predictions using per-class confidence thresholds.

    Subject tokens are weighted 3x in the input to match training-time
    feature weighting. Returns None if models unavailable or all predictions
    fall below their class-specific thresholds.
    """
    models, meta = _get_models(db_path)
    if not models:
        _log.debug("local_classifier: predict skipped — no trained model available")
        return None

    # Build the same combined input used at training time
    combined = f"{subject_tokens} {subject_tokens} {subject_tokens} {body_text}".strip()

    result: dict[str, Any] = {
        "analysis_engine": "local-classifier",
        "model_version": meta.get("version_id", "unknown"),
    }
    confidence_scores: dict[str, float] = {}
    any_prediction = False

    for target, model in models.items():
        try:
            proba = model.predict_proba([combined])[0]
            max_prob = float(max(proba))
            pred = str(model.classes_[proba.argmax()])
            confidence_scores[target] = round(max_prob, 3)

            # Determine threshold: per-class override > per-target default
            threshold = _CLASS_THRESHOLDS.get(pred, _TARGET_THRESHOLDS.get(target, _DEFAULT_CONFIDENCE_THRESHOLD))
            if max_prob >= threshold:
                result[target] = pred
                any_prediction = True
        except Exception as exc:
            _log.warning("local_classifier: predict error target=%s: %s", target, exc)

    result["classifier_confidence_scores"] = confidence_scores

    if not any_prediction:
        _log.debug(
            "local_classifier: predict declined — all targets below confidence threshold "
            "(scores: %s)",
            confidence_scores,
        )
        return None

    return result
