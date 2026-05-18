# Local Classifier

Last updated: 2026-05-18

## Purpose

ReplyRight's local classifier reduces API dependency by learning structured hotel email labels from reviewed training examples.

It predicts:

- Urgency
- Owner
- Category

The classifier does not write replies. It is a structured-label model that supports the broader deterministic and AI-assisted triage pipeline.

## Implementation

Module:

```text
outlook_dashboard/local_classifier.py
```

Model shape:

```text
Supabase training_examples
  -> human_reviewed=true rows
  -> subject_tokens weighted 3x
  -> body_redacted
  -> TfidfVectorizer
  -> Calibrated LogisticRegression
  -> one pipeline per target
  -> pickle bundle in local SQLite app_kv
```

The implementation uses:

- TF-IDF features with unigrams through trigrams.
- Subject weighting by repeating `subject_tokens` three times.
- `LogisticRegression` with balanced class weights.
- `CalibratedClassifierCV` for probability estimates.
- Per-target and per-class confidence thresholds.
- Cross-validation accuracy reporting where enough data exists.
- Feature importance extraction from top TF-IDF terms.

## Training Source

Training examples come from Supabase `training_examples`.

The classifier downloads:

- `subject_tokens`
- `body_redacted`
- `label_urgency`
- `label_owner`
- `label_category`
- `labeling_engine`

Only `human_reviewed=true` rows are used.

Minimum training examples:

```text
20
```

Each target also needs at least two valid classes and enough labeled rows.

## Persistence

Model artifacts are stored in local SQLite `app_kv`:

- `local_classifier_models`
- `local_classifier_models_prev`
- `local_classifier_meta`

Each training run stamps metadata with:

- `version_id`
- `trained_at`
- total downloaded examples
- target-level examples
- class counts
- label distribution
- cross-validation accuracy
- feature importance

The previous model blob is retained for rollback support. A full admin rollback flow is still a future hardening item.

## Runtime Prediction

`predict(body_text, subject_tokens="", db_path=None)` returns `None` when:

- No model is stored.
- All target predictions fall below confidence thresholds.
- Prediction errors occur.

When prediction succeeds, it returns fields such as:

```json
{
  "analysis_engine": "local-classifier",
  "model_version": "20260518T120000Z",
  "urgency": "3",
  "owner": "Reservations",
  "category": "Rate inquiry",
  "classifier_confidence_scores": {
    "urgency": 0.81,
    "owner": 0.77,
    "category": 0.69
  }
}
```

`ai.py` attempts classifier prediction before deterministic/external fallback.

## Confidence Thresholds

Default threshold:

```text
0.60
```

Target-level thresholds:

- Urgency: `0.62`
- Owner: `0.58`
- Category: `0.55`

Selected rare or risky classes have lower thresholds so they are not impossible to predict:

- Accessibility request
- Billing dispute
- Urgent same-day arrival
- Complaint
- Duplicate follow-up

Risk handling must still remain conservative; a classifier prediction should not hide risk flags.

## Admin Endpoints

- `POST /api/admin/classifier/train`
- `GET /api/admin/classifier/status`
- `GET /api/admin/classifier/feature-importance`

Names may vary slightly by route implementation; check `outlook_dashboard/main.py` before adding new UI calls.

## Verification

Targeted source tests:

```powershell
python -m pytest tests/test_training_pipeline.py tests/test_ai_and_database.py -v
```

Full suite:

```powershell
python -m pytest tests/ -x
```

Manual admin smoke:

1. Confirm Supabase `training_examples` has reviewed rows.
2. Run classifier training from Admin.
3. Confirm status shows model metadata.
4. Confirm feature importance renders.
5. Refresh or analyze routine emails and confirm classifier predictions are visible only when thresholds are met.

## Failure Modes

- Too few reviewed examples: training returns `trained=false`.
- Class imbalance: a target may train poorly or skip if only one class exists.
- Unreviewed labels: examples are visible but ignored for training.
- Missing sklearn bundle in EXE: packaged classifier import may fail; keep PyInstaller sklearn/joblib/threadpoolctl flags in `build_exe.ps1`.
- Stale model: app may continue using an old local SQLite model until retrained or replaced.

## Future Work

- Explicit model rollback endpoint/UI.
- Candidate vs active model comparison.
- Held-out evaluation set and confusion matrices.
- Prediction logging.
- Classifier health dashboard with correction-rate trends.
- Contact type, status, reply required, escalation required, and no-action targets.
