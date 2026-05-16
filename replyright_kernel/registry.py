"""
Plugin registry — single place to add/remove kernel plugins.

Future engineers: add new plugin registrations in the clearly labelled
extension sections below. Keep plugins grouped by capability tier
(local-only, Graph/external read, CRM lookup, write-back if ever approved).
"""
from __future__ import annotations

import logging

from semantic_kernel import Kernel

from .plugins.audit_compliance import AuditCompliancePlugin
from .plugins.executive_summary import ExecutiveSummaryPlugin
from .plugins.priority_triage import PriorityTriagePlugin

logger = logging.getLogger(__name__)


def register_plugins(kernel: Kernel) -> None:
    """Register all native plugins into the kernel workspace."""

    # ── Tier 1: Local deterministic plugins (zero API cost) ──────────────────
    kernel.add_plugin(PriorityTriagePlugin(), plugin_name="PriorityTriage")
    logger.debug("Registered plugin: PriorityTriage")

    kernel.add_plugin(ExecutiveSummaryPlugin(), plugin_name="ExecutiveSummary")
    logger.debug("Registered plugin: ExecutiveSummary")

    kernel.add_plugin(AuditCompliancePlugin(), plugin_name="AuditCompliance")
    logger.debug("Registered plugin: AuditCompliance")

    # ── FUTURE Tier 2: Microsoft Graph Outlook read plugins ───────────────────
    # Prerequisite: Entra app registration + Mail.Read.Shared permission approved.
    # See docs/DECISIONS.md — Outlook stays read-only.
    #
    #   from replyright_kernel.plugins.graph_mail import GraphMailPlugin
    #   graph_client = build_graph_client(settings)
    #   kernel.add_plugin(GraphMailPlugin(graph_client), plugin_name="GraphMail")
    #
    # GraphMailPlugin should expose:
    #   list_messages(folder, top) → list of message summaries
    #   get_thread(message_id)     → full thread text
    #   get_attachments(message_id)→ attachment metadata (names/sizes, not content)
    # ─────────────────────────────────────────────────────────────────────────

    # ── FUTURE Tier 3: Internal CRM lookup plugins ────────────────────────────
    # Register when a CRM integration is approved and credentials are available.
    #
    #   from replyright_kernel.plugins.crm import CRMLookupPlugin
    #   crm_client = build_crm_client(settings)
    #   kernel.add_plugin(CRMLookupPlugin(crm_client), plugin_name="CRMLookup")
    #
    # CRMLookupPlugin should expose:
    #   lookup_guest(email)         → guest profile dict
    #   get_reservation(conf_number)→ reservation details
    #   get_vip_profile(guest_id)   → VIP flags and preferences
    # ─────────────────────────────────────────────────────────────────────────

    logger.info(
        "Plugin registry complete. Active: PriorityTriage, ExecutiveSummary, AuditCompliance."
    )
