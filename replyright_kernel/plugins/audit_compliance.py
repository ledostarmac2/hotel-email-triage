"""
AuditCompliancePlugin — local pre-display compliance scanner.

Scans generated draft replies before they are shown to the user.
Runs entirely locally with no LLM cost. Blocks or sanitises drafts
that contain guarantees, fault admissions, payment data, legal/medical
risk language, discrimination risk, or unapproved promises.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from semantic_kernel.functions import kernel_function

# ── Rule patterns ─────────────────────────────────────────────────────────────

_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "guarantee_or_concession",
        re.compile(
            r"\b(we guarantee|i guarantee|guaranteed|we promise|i promise"
            r"|you will (?:receive|get|have)"
            r"|we will (?:definitely|absolutely|certainly) (?:arrange|provide|confirm|ensure))\b",
            re.IGNORECASE,
        ),
        "Remove absolute guarantees; use 'subject to availability' or 'pending confirmation'.",
    ),
    (
        "admission_of_fault",
        re.compile(
            r"\b(we (?:are|were) (?:at fault|wrong|responsible|liable)"
            r"|our (?:fault|mistake|error)"
            r"|we (?:sincerely )?apologize for (?:the|our) (?:fault|mistake|error|negligence))\b",
            re.IGNORECASE,
        ),
        "Replace direct fault admission with empathetic acknowledgment pending review.",
    ),
    (
        "payment_leakage",
        re.compile(
            r"\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}" r"|cvv|card number|security code|full card)\b",
            re.IGNORECASE,
        ),
        "Remove any payment card data from the draft before sharing.",
    ),
    (
        "legal_risk_language",
        re.compile(
            r"\b(we are not liable|not our responsibility|no liability"
            r"|waive (?:all )?liability|without (?:any )?recourse"
            r"|legal action will (?:not )?(?:be|result))\b",
            re.IGNORECASE,
        ),
        "Remove liability disclaimers; legal posture requires management sign-off.",
    ),
    (
        "medical_risk_language",
        re.compile(
            r"\b(we (?:can )?accommodate (?:any|all) (?:medical|health)"
            r"|medically (?:safe|suitable|approved)|no (?:medical|health) risk)\b",
            re.IGNORECASE,
        ),
        "Do not make medical safety claims; escalate to Accessibility Coordinator.",
    ),
    (
        "discrimination_risk_language",
        re.compile(
            r"\b(we do not discriminate.*?but"
            r"|that.s our policy for (?:your type|people like)"
            r"|(?:race|religion|nationality|gender|age|disability) (?:is not|isn.t|are not|aren.t) (?:a )?factor)\b",
            re.IGNORECASE,
        ),
        "Flag for immediate management review; do not send.",
    ),
    (
        "unapproved_promise",
        re.compile(
            r"\b(you will (?:definitely )?get (?:a |the )?(?:upgrade|room|suite|view)"
            r"|(?:early check[- ]in|late check[- ]out) is (?:confirmed|arranged|yours)"
            r"|we.ve (?:already )?reserved"
            r"|complimentary \w+ is (?:confirmed|ready))\b",
            re.IGNORECASE,
        ),
        "Replace confirmed promises with 'subject to availability' phrasing.",
    ),
    (
        "blacklisted_language",
        re.compile(
            r"\b(off the record|just between us|don.t (?:tell|share) this"
            r"|internal only|confidential(?:ly)?|secret(?:ly)?)\b",
            re.IGNORECASE,
        ),
        "Remove internal-only or off-record language from guest-facing drafts.",
    ),
]


@dataclass
class AuditResult:
    approved: bool
    violations: list[str]
    sanitized_draft: str
    recommended_fix_notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "violations": self.violations,
            "sanitized_draft": self.sanitized_draft,
            "recommended_fix_notes": self.recommended_fix_notes,
        }


class AuditCompliancePlugin:
    """
    Pre-display compliance gate. Runs after LLM draft generation but before
    the draft is shown to the user. Never touches Outlook messages.
    """

    @kernel_function(
        name="audit",
        description=(
            "Scan a draft reply for compliance violations. "
            "Returns approved bool, violations list, sanitized_draft, "
            "and recommended_fix_notes. No LLM required."
        ),
    )
    def audit(self, draft: str = "") -> dict[str, Any]:
        violations: list[str] = []
        fix_notes: list[str] = []
        sanitized = draft

        for rule_name, pattern, fix_note in _RULES:
            if pattern.search(sanitized):
                violations.append(rule_name)
                fix_notes.append(fix_note)
                sanitized = pattern.sub(f"[BLOCKED:{rule_name}]", sanitized)

        return AuditResult(
            approved=len(violations) == 0,
            violations=violations,
            sanitized_draft=sanitized,
            recommended_fix_notes=fix_notes,
        ).to_dict()
