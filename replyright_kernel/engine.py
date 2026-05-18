"""
Kernel engine factory.

Call build_kernel() to get a fully configured Semantic Kernel instance
with all native plugins registered and the OpenAI chat service attached
(when OPENAI_API_KEY is present).
"""

from __future__ import annotations

import logging

from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

from .registry import register_plugins
from .settings import KernelSettings, get_kernel_settings

logger = logging.getLogger(__name__)


def build_kernel(settings: KernelSettings | None = None) -> Kernel:
    """
    Build and return a configured Semantic Kernel instance.

    When OPENAI_API_KEY is absent the kernel still works for local-only
    plugin calls (PriorityTriage, ExecutiveSummary, AuditCompliance).
    """
    if settings is None:
        settings = get_kernel_settings()

    kernel = Kernel()

    if settings.api_key_configured:
        service = OpenAIChatCompletion(
            service_id="default",
            ai_model_id=settings.openai_model,
            api_key=settings.openai_api_key,
        )
        kernel.add_service(service)
        logger.info("OpenAI chat service registered: model=%s", settings.openai_model)
    else:
        logger.warning(
            "OPENAI_API_KEY not set — OpenAI service not registered. "
            "Local plugins will work; invoke_prompt calls will fail."
        )

    register_plugins(kernel)
    return kernel
