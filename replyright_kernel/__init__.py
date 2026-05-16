"""
ReplyRight Semantic Kernel orchestration layer.

Entry points:
    build_kernel()        — returns a fully configured Kernel instance
    get_kernel_settings() — returns typed settings from environment
"""

from .engine import build_kernel
from .settings import KernelSettings, get_kernel_settings

__all__ = ["build_kernel", "get_kernel_settings", "KernelSettings"]
