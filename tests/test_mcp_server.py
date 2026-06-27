import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


def load_server_module():
    path = Path(__file__).resolve().parents[1] / "mcp" / "llm_council_server.py"
    spec = importlib.util.spec_from_file_location("llm_council_mcp_server", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class McpServerLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = load_server_module()

    def test_ensure_backend_reuses_healthy_backend(self):
        with patch.object(self.server, "_health_payload", return_value={"ok": True}), \
             patch.object(self.server, "_start_backend") as start_backend:
            self.server.ensure_backend()

        start_backend.assert_not_called()

    def test_ensure_backend_starts_when_unavailable(self):
        with patch.object(self.server, "_health_payload", side_effect=[None, {"ok": True}]), \
             patch.object(self.server, "_start_backend") as start_backend, \
             patch.object(self.server.time, "sleep"):
            self.server.ensure_backend()

        start_backend.assert_called_once()

    def test_start_backend_rejects_wrong_service_on_port(self):
        with patch.object(self.server, "_port_is_open", return_value=True), \
             patch.object(self.server, "_health_payload", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Port 8001 is occupied"):
                self.server._start_backend()


if __name__ == "__main__":
    unittest.main()
