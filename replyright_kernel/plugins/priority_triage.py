"""
PriorityTriagePlugin — local urgency evaluator.

Runs before any LLM call. Uses regex rules, keyword matching, sender domain
checks, importance markers, and escalation signals to score urgency 1-5.
No API cost; safe to run on every message at bulk-refresh time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from semantic_kernel.functions import kernel_function

# ── Compiled patterns ─────────────────────────────────────────────────────────

_VIP_TERMS = re.compile(
    r"\b(vip|executive|owner|celebrity|c-suite|ceo|cfo|coo|president|chairman|board\s+member)\b",
    re.IGNORECASE,
)
_SAME_DAY_TERMS = re.compile(
    r"\b(same[- ]day|today|tonight|this evening|arriving now|already here|on my way)\b",
    re.IGNORECASE,
)
_ESCALATION_TERMS = re.compile(
    r"\b(urgent|asap|immediately|right away|right now|emergency|as soon as possible|critical)\b",
    re.IGNORECASE,
)
_LEGAL_TERMS = re.compile(
    r"\b(lawyer|attorney|lawsuit|litigation|legal action|court|sue\b|claim|arbitration)\b",
    re.IGNORECASE,
)
_MEDICAL_TERMS = re.compile(
    r"\b(medical|doctor|hospital|ambulance|allerg(y|ic)|injury|injured|medication|epipen)\b",
    re.IGNORECASE,
)
_DISCRIMINATION_TERMS = re.compile(
    r"\b(discriminat\w*|harassment|hostile\s+environment|bias|prejudice|racial|ageism|ableism)\b",
    re.IGNORECASE,
)
_BILLING_TERMS = re.compile(
    r"\b(billing|chargeback|dispute|refund|overcharged|double[- ]charge|fraud|unauthorized charge)\b",
    re.IGNORECASE,
)
_ACCESSIBILITY_TERMS = re.compile(
    r"\b(wheelchair|roll[- ]in shower|ada\b|accessible|hearing[- ]impaired|"
    r"visual(ly)?[- ]impaired|mobility|service animal|shower chair)\b",
    re.IGNORECASE,
)
_FOLLOW_UP_TERMS = re.compile(
    r"\b(following up|follow[- ]up|checking in again|second request|third request|"
    r"no response|still waiting|haven.t heard)\b",
    re.IGNORECASE,
)
_IMPORTANCE_KEYWORDS = re.compile(
    r"\b(high importance|high priority|flagged as important|marked important)\b",
    re.IGNORECASE,
)

_SENSITIVE_SENDER_DOMAINS: frozenset[str] = frozenset({
    "tripadvisor.com",
    "yelp.com",
    "google.com",
    "opentable.com",
    "hvs.com",
    "jll.com",
})
_INTERNAL_SENDER_DOMAINS: frozenset[str] = frozenset({
    "hilton.com",
    "waldorfastoria.com",
})

_PRIORITY_LABELS: dict[int, str] = {
    1: "Low",
    2: "Normal",
    3: "Elevated",
    4: "High",
    5: "Immediate",
}


@dataclass
class TriageResult:
    urgency_score: int
    priority_label: str
    matched_rules: list[str]
    risk_flags: list[str]
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "urgency_score": self.urgency_score,
            "priority_label": self.priority_label,
            "matched_rules": self.matched_rules,
            "risk_flags": self.risk_flags,
            "explanation": self.explanation,
        }


class PriorityTriagePlugin:
    """
    Evaluates email urgency locally before any LLM inference.
    Returns structured triage metadata used to frame the LLM prompt
    and decide whether escalation is needed.
    """

    @kernel_function(
        name="triage",
        description=(
            "Evaluate email urgency using local rules. "
            "Returns urgency_score 1-5, priority_label, matched_rules, "
            "risk_flags, and explanation. No LLM required."
        ),
    )
    def triage(
        self,
        subject: str = "",
        body: str = "",
        sender_email: str = "",
        importance: str = "",
    ) -> dict[str, Any]:
        text = f"{subject}\n{body}"
        matched_rules: list[str] = []
        risk_flags: list[str] = []
        score = 2  # default: Normal

        # Outlook importance flag
        if (importance or "").lower() == "high":
            score = max(score, 3)
            matched_rules.append("outlook_importance_high")
        if _IMPORTANCE_KEYWORDS.search(text):
            score = max(score, 3)
            matched_rules.append("importance_keyword")

        # Same-day / tonight language → at least High
        if _SAME_DAY_TERMS.search(text):
            score = max(score, 4)
            matched_rules.append("same_day_language")

        # Escalation words → at least High
        if _ESCALATION_TERMS.search(text):
            score = max(score, 4)
            matched_rules.append("escalation_language")

        # VIP / executive terms → at least Elevated
        if _VIP_TERMS.search(text):
            score = max(score, 3)
            matched_rules.append("vip_executive_language")
            risk_flags.append("VIP")

        # Billing / payment risk → at least High
        if _BILLING_TERMS.search(text):
            score = max(score, 4)
            matched_rules.append("billing_payment_risk")
            risk_flags.append("Billing")

        # Accessibility → at least High
        if _ACCESSIBILITY_TERMS.search(text):
            score = max(score, 4)
            matched_rules.append("accessibility_language")
            risk_flags.append("ADA_accessibility")

        # Legal risk → Immediate
        if _LEGAL_TERMS.search(text):
            score = 5
            matched_rules.append("legal_risk_language")
            risk_flags.append("Legal")

        # Medical risk → Immediate
        if _MEDICAL_TERMS.search(text):
            score = 5
            matched_rules.append("medical_risk_language")
            risk_flags.append("Medical")

        # Discrimination risk → Immediate
        if _DISCRIMINATION_TERMS.search(text):
            score = 5
            matched_rules.append("discrimination_risk_language")
            risk_flags.append("Discrimination")

        # Follow-up / repeated contact → at least Elevated
        if _FOLLOW_UP_TERMS.search(text):
            score = max(score, 3)
            matched_rules.append("follow_up_marker")

        # Sender domain checks
        sender_domain = ""
        if "@" in (sender_email or ""):
            sender_domain = sender_email.lower().split("@")[-1]
        if sender_domain in _SENSITIVE_SENDER_DOMAINS:
            score = max(score, 3)
            matched_rules.append(f"sensitive_sender_domain:{sender_domain}")
            risk_flags.append("Reputation_risk")
        if sender_domain in _INTERNAL_SENDER_DOMAINS:
            score = max(score, 3)
            matched_rules.append(f"internal_sender_domain:{sender_domain}")

        score = max(1, min(5, score))
        priority_label = _PRIORITY_LABELS[score]
        explanation = (
            f"Score {score}/5 ({priority_label}). "
            f"Rules matched: {matched_rules or ['none']}. "
            f"Risk flags: {risk_flags or ['none']}."
        )

        return TriageResult(
            urgency_score=score,
            priority_label=priority_label,
            matched_rules=matched_rules,
            risk_flags=risk_flags,
            explanation=explanation,
        ).to_dict()
