from __future__ import annotations

import logging

from semantic_kernel import Kernel

from .plugins.audit_compliance import AuditCompliancePlugin
from .plugins.executive_summary import ExecutiveSummaryPlugin
from .plugins.priority_triage import PriorityTriagePlugin

logger = logging.getLogger(__name__)

_PLUGINS = [
    (PriorityTriagePlugin, "PriorityTriage"),
    (ExecutiveSummaryPlugin, "ExecutiveSummary"),
    (AuditCompliancePlugin, "AuditCompliance"),
]


def register_plugins(kernel: Kernel) -> None:
    """Register all native plugins into the kernel workspace."""
    for cls, name in _PLUGINS:
        kernel.add_plugin(cls(), plugin_name=name)
        logger.debug("Registered plugin: %s", name)
    logger.info("Plugin registry complete. Active: %s.", ", ".join(n for _, n in _PLUGINS))

    # ── FUTURE Tier 2: Microsoft Graph Outlook read plugins ───────────────────
    # Prerequisite: Entra app registration + Mail.Read.Shared permission approved.
    # See docs/DECISIONS.md — Outlook stays read-only.
    #
    #   from replyright_kernel.plugins.graph_mail import GraphMailPlugin
    #   kernel.add_plugin(GraphMailPlugin(build_graph_client(settings)), plugin_name="GraphMail")
    #
    # Expose: list_messages(folder, top), get_thread(message_id), get_attachments(message_id)
    # ─────────────────────────────────────────────────────────────────────────

    # ── FUTURE Tier 3: Internal CRM lookup plugins ────────────────────────────
    # Register when a CRM integration is approved and credentials are available.
    #
    #   from replyright_kernel.plugins.crm import CRMLookupPlugin
    #   kernel.add_plugin(CRMLookupPlugin(build_crm_client(settings)), plugin_name="CRMLookup")
    #
    # Expose: lookup_guest(email), get_reservation(conf_number), get_vip_profile(guest_id)
    # ─────────────────────────────────────────────────────────────────────────
