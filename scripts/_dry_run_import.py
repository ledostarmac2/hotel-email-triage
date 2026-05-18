"""Dry-run the import: print per-email outcomes without writing to Supabase."""
import sys
sys.path.insert(0, ".")
from outlook_dashboard.config import _load_env
_load_env()
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("import_labels", "scripts/import_labels.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

ROOT = Path(".")
claude_path = mod._find_date_file(ROOT / "labeling" / "Claude", "2026-05-18")
chatgpt_path = mod._find_date_file(ROOT / "labeling" / "ChatGPT", "2026-05-18")
print("Claude file:", claude_path)
print("ChatGPT file:", chatgpt_path)

claude_rows = mod._load_json_file(claude_path)
chatgpt_rows_raw = mod._load_json_file(chatgpt_path)
claude_idx = {r["training_example_id"]: r for r in claude_rows if r.get("training_example_id")}
chatgpt_idx = {}
for row in chatgpt_rows_raw:
    tid = row.get("training_example_id")
    if not tid:
        continue
    if mod._is_critic_format(row):
        chatgpt_idx[tid] = mod._normalize_critic_to_labels(row, claude_idx.get(tid, {}))
    else:
        chatgpt_idx[tid] = row

print(f"Claude rows: {len(claude_idx)}  ChatGPT rows: {len(chatgpt_idx)}")
outcomes = {"dual_labeled": 0, "partial": 0, "needs_review": 0}
for tid in sorted(set(claude_idx) | set(chatgpt_idx)):
    c = claude_idx.get(tid)
    g = chatgpt_idx.get(tid)
    if not c or not g:
        outcomes["needs_review"] += 1
        print(f"  {tid[:8]}  only-one-source -> needs_review")
        continue
    n, agreed, disagreed = mod._count_agreements(c, g)
    if n == 6:
        outcomes["dual_labeled"] += 1
        label = "dual"
    elif n >= 4:
        outcomes["partial"] += 1
        label = "partial"
    else:
        outcomes["needs_review"] += 1
        label = "review"
    print(f"  {tid[:8]}  {n}/6  {label}  disagreed={disagreed}")
print()
print("Summary:", outcomes)
