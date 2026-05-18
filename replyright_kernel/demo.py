"""
ReplyRight Kernel — end-to-end demo pipeline.

Run from the repo root:
    python -m replyright_kernel.demo

Pipeline (token-saving architecture):
    1. ExecutiveSummaryPlugin  — strip HTML / quoted threads / footers  (local)
    2. PriorityTriagePlugin    — score urgency 1-5                      (local)
    3. Semantic Kernel + LLM   — draft reply on lean payload            (API)
    4. AuditCompliancePlugin   — compliance scan before display         (local)

Steps 1, 2, 4 consume zero API tokens.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from .engine import build_kernel
from .plugins.audit_compliance import AuditCompliancePlugin
from .plugins.executive_summary import ExecutiveSummaryPlugin
from .plugins.priority_triage import PriorityTriagePlugin
from .settings import get_kernel_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# ── Demo email — realistic messy Outlook thread ───────────────────────────────
DEMO_EMAIL: dict[str, Any] = {
    "subject": "URGENT - Accessible room + VIP CEO arriving TONIGHT - Third request",
    "sender_name": "Marcus Chen",
    "sender_email": "marcus.chen@examplecorp.com",
    "importance": "high",
    "raw_content": """\
<html><body>
<p>Hi,</p>
<p>I am following up for the <b>third time</b> on our booking for <em>tonight</em>. Our
CEO, Ms. Eleanor Vance, requires a wheelchair-accessible suite with a roll-in shower.
We were told this was available when we booked (Confirmation: RES-88234).</p>

<p>This is now urgent — she arrives in 4 hours. If this is not resolved I will be
escalating to our legal team and will post a review on TripAdvisor.</p>

<p>Best,<br/>Marcus Chen<br/>Executive Assistant to the CEO<br/>ExampleCorp Inc.</p>
<hr/>
-----Original Message-----
From: reservations@hotel.com
Sent: Monday, May 13, 2026 09:14 AM
To: marcus.chen@examplecorp.com
Subject: RE: Accessible room request

<p>Dear Mr. Chen,</p>
<p>Thank you for your message. We will review this and get back to you.</p>
<p>Warm regards,<br/>Reservations Team</p>

<p>This email and any attachments are confidential and intended solely for the use of
the individual or entity to whom it is addressed. If you have received this message
in error, please notify the sender immediately and delete it from your system.</p>

<p>Unsubscribe | View in browser | &copy; 2026 Hotel Systems LLC. All rights reserved.</p>
</body></html>
""",
}

_DRAFT_PROMPT = """\
You are an expert hotel reservations assistant for a luxury property. Write a concise,
warm, professional draft reply for the email thread below.

Rules:
- Do not guarantee outcomes not yet confirmed. Use "subject to availability."
- Do not admit fault. Use empathetic but neutral acknowledgment.
- Do not invent rates, policies, or availability.
- Address the guest formally (Mr./Ms. Last Name).
- Keep the draft under 200 words.

Email thread (cleaned and token-optimised):
{clean_content}

Triage metadata:
- Urgency: {urgency_score}/5 ({priority_label})
- Risk flags: {risk_flags}
- Matched rules: {matched_rules}

Draft reply:"""


async def run_pipeline(
    email: dict[str, Any],
    kernel: Any | None = None,
) -> dict[str, Any]:
    """
    Run the full four-step pipeline on one email dict.

    Args:
        email: dict with keys subject, sender_name, sender_email, importance,
               raw_content (HTML or plain text).
        kernel: optional pre-built Kernel (useful for testing with mocks).

    Returns:
        dict with clean_content, triage, draft, audit, llm_error.
    """
    settings = get_kernel_settings()
    if kernel is None:
        kernel = build_kernel(settings)

    # ── Step 1: Clean the thread ──────────────────────────────────────────────
    summary_plugin = ExecutiveSummaryPlugin()
    clean_content = summary_plugin.clean(raw_content=email.get("raw_content", ""))
    logger.info("ExecutiveSummary: cleaned to %d chars", len(clean_content))

    # ── Step 2: Local urgency triage ──────────────────────────────────────────
    triage_plugin = PriorityTriagePlugin()
    triage: dict[str, Any] = triage_plugin.triage(
        subject=email.get("subject", ""),
        body=clean_content,
        sender_email=email.get("sender_email", ""),
        importance=email.get("importance", ""),
    )
    logger.info(
        "PriorityTriage: score=%d label=%s flags=%s",
        triage["urgency_score"],
        triage["priority_label"],
        triage["risk_flags"],
    )

    # ── Step 3: LLM draft (lean, token-optimised payload only) ───────────────
    draft = ""
    llm_error: str | None = None

    if settings.api_key_configured:
        try:
            prompt = _DRAFT_PROMPT.format(
                clean_content=clean_content,
                urgency_score=triage["urgency_score"],
                priority_label=triage["priority_label"],
                risk_flags=", ".join(triage["risk_flags"]) or "none",
                matched_rules=", ".join(triage["matched_rules"]) or "none",
            )
            result = await kernel.invoke_prompt(prompt_template_string=prompt)
            draft = str(result).strip()
            logger.info("LLM draft generated: %d chars", len(draft))
        except Exception as exc:
            llm_error = str(exc)[:300]
            logger.error("LLM draft generation failed: %s", llm_error)
    else:
        sender_last = (email.get("sender_name") or "Guest").split()[-1]
        draft = (
            f"Dear Mr./Ms. {sender_last},\n\n"
            "Thank you for reaching out. We are urgently reviewing your request "
            "and will follow up with confirmed information as soon as possible.\n\n"
            "Warm regards,\nReservations Team"
        )
        logger.warning("No API key — placeholder draft used.")

    # ── Step 4: Compliance audit before display ───────────────────────────────
    audit_plugin = AuditCompliancePlugin()
    audit: dict[str, Any] = audit_plugin.audit(draft=draft)
    logger.info(
        "AuditCompliance: approved=%s violations=%s",
        audit["approved"],
        audit["violations"],
    )

    return {
        "clean_content": clean_content,
        "triage": triage,
        "draft": draft,
        "audit": audit,
        "llm_error": llm_error,
    }


async def _main() -> None:
    result = await run_pipeline(DEMO_EMAIL)

    SEP = "=" * 70
    print(f"\n{SEP}")
    print("REPLYRIGHT KERNEL — DEMO PIPELINE RESULT")
    print(SEP)

    t = result["triage"]
    print(f"\n[TRIAGE]  Score : {t['urgency_score']}/5 — {t['priority_label']}")
    print(f"          Rules : {t['matched_rules']}")
    print(f"          Flags : {t['risk_flags']}")
    print(f"          Notes : {t['explanation']}")

    a = result["audit"]
    status = "APPROVED" if a["approved"] else "BLOCKED"
    print(f"\n[AUDIT]   Status     : {status}")
    if a["violations"]:
        print(f"          Violations : {a['violations']}")
        for note in a["recommended_fix_notes"]:
            print(f"          Fix note   : {note}")

    print("\n[DRAFT]")
    if a["approved"]:
        print(result["draft"])
    else:
        print("(Draft blocked by compliance audit. Sanitised version:)")
        print(a["sanitized_draft"])

    if result.get("llm_error"):
        print(f"\n[ERROR] LLM call failed: {result['llm_error']}")

    print(f"\n{SEP}\n")


if __name__ == "__main__":
    asyncio.run(_main())
