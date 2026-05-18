from __future__ import annotations

import importlib
import unittest


class ImportSmokeTests(unittest.TestCase):
    def test_active_python_modules_import_cleanly(self) -> None:
        modules = [
            "outlook_dashboard.ai",
            "outlook_dashboard.auth",
            "outlook_dashboard.config",
            "outlook_dashboard.database",
            "outlook_dashboard.graph",
            "outlook_dashboard.main",
            "outlook_dashboard.outlook_desktop",
            "outlook_dashboard.redaction",
            "outlook_dashboard.runtime_log",
            "outlook_dashboard.supabase_client",
            "outlook_dashboard.taxonomy",
            "replyright_kernel.engine",
            "replyright_kernel.registry",
            "replyright_kernel.demo",
            "replyright_kernel.plugins.audit_compliance",
            "replyright_kernel.plugins.executive_summary",
            "replyright_kernel.plugins.priority_triage",
        ]
        for module_name in modules:
            with self.subTest(module=module_name):
                importlib.import_module(module_name)


if __name__ == "__main__":
    unittest.main()
