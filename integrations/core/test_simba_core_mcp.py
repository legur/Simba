"""Offline MCP stdio handshake and non-billable regression tests."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "plugins/simba-core/server/simba_core_mcp.py"
spec = importlib.util.spec_from_file_location("simba_core_mcp_test_target", SERVER)
mcp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcp)


def mcp_request(method, id=1, params=None):
    return {"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}}


class SimbaCoreMCPContractTests(unittest.TestCase):
    def test_server_can_initialize_and_list_all_tools(self):
        init = mcp.handle(mcp_request("initialize"))
        self.assertEqual(init["result"]["serverInfo"]["name"], "simba-core-private-pilot")
        self.assertIn("tools", init["result"]["capabilities"])
        available = mcp.handle(mcp_request("tools/list"))["result"]["tools"]
        names = {t["name"] for t in available}
        self.assertEqual(names, {
            "simba_core_preflight",
            "simba_core_run_private_pilot",
            "simba_core_audit_pilot_receipts",
            "simba_core_read_pilot_text",
        })
        paid = next(x for x in available if x["name"] == "simba_core_run_private_pilot")
        self.assertFalse(paid["annotations"]["readOnlyHint"])
        self.assertTrue(paid["annotations"]["openWorldHint"])
        self.assertIn("permit_billable_api_calls", paid["inputSchema"]["required"])

    def test_no_message_for_notifications(self):
        self.assertIsNone(mcp.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_no_key_preflight_reports_not_executed(self):
        with patch.dict(os.environ, {"SIMBA_CORE_REPO_ROOT": str(ROOT),
                                     "OPENAI_API_KEY": "",
                                     "SIMBA_CORE_ALLOW_BILLABLE": ""}):
            result = mcp.preflight()
        self.assertEqual(result["status"], "BLOCKED_LIVE_EXECUTOR_NOT_RUN")
        self.assertFalse(result["live_calls_made"])
        self.assertFalse(result["local_pilot_configured"])
        self.assertIn("OPENAI_API_KEY_NOT_CONFIGURED", result["preflight_blockers"])

    def test_billing_flags_and_local_operator_gate_required(self):
        with patch.dict(os.environ, {"SIMBA_CORE_REPO_ROOT": str(ROOT),
                                     "OPENAI_API_KEY": "fake-test-key",
                                     "SIMBA_CORE_ALLOW_BILLABLE": ""}):
            for args, expected in [
                ({}, "EXPLICIT_LIVE_FLAG_REQUIRED"),
                ({"execute_live": True}, "EXPLICIT_BILLABLE_FLAG_REQUIRED"),
                ({"execute_live": True, "permit_billable_api_calls": True},
                 "LOCAL_BILLABLE_GATE_DISABLED"),
            ]:
                with self.subTest(expected=expected):
                    with self.assertRaisesRegex(mcp.BridgeBlocked, expected):
                        mcp.run_private_pilot(args)

    def test_tool_call_returns_error_without_any_api_calls(self):
        request = mcp_request("tools/call", params={
            "name": "simba_core_run_private_pilot",
            "arguments": {"brief": "Только тест.", "model": "gpt-6",
                          "execute_live": False, "permit_billable_api_calls": True},
        })
        result = mcp.handle(request)["result"]
        self.assertTrue(result["isError"])
        self.assertIn("EXPLICIT_LIVE_FLAG_REQUIRED", result["content"][0]["text"])

    def test_run_id_cannot_traverse_private_paths(self):
        for item in ("../secrets", "/tmp/other", "not-uuid", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa/.."):
            with self.subTest(run_id=item):
                with self.assertRaisesRegex(mcp.BridgeBlocked, "INVALID_RUN_ID"):
                    mcp._get_private_run_files(item)

    def test_missing_repo_not_substituted_from_model_memory(self):
        with patch.dict(os.environ, {"SIMBA_CORE_REPO_ROOT": ""}):
            with self.assertRaisesRegex(mcp.BridgeBlocked, "SIMBA_CORE_REPO_ROOT_NOT_CONFIGURED"):
                mcp.repo_root()

    def test_stdio_jsonrpc_roundtrip_has_no_diagnostic_stdout(self):
        process = subprocess.run(
            [sys.executable, str(SERVER)],
            input="\n".join([
                json.dumps(mcp_request("initialize")),
                json.dumps(mcp_request("tools/list", id=2)),
                json.dumps(mcp_request("tools/call", id=3, params={
                    "name": "simba_core_run_private_pilot", "arguments": {},
                })),
                "",
            ]),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=15,
            env={**os.environ, "OPENAI_API_KEY": "", "SIMBA_CORE_ALLOW_BILLABLE": ""},
        )
        self.assertEqual(process.returncode, 0)
        replies = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual([x["id"] for x in replies], [1, 2, 3])
        self.assertTrue(replies[2]["result"]["isError"])
        self.assertNotIn("Bearer", process.stdout)
        self.assertNotIn("simulated pass", process.stdout.lower())

    def test_windows_setup_script_has_no_billable_call_or_secrets(self):
        text = (ROOT / "plugins/simba-core/setup_simba_core_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("simba_core_preflight", text)
        self.assertIn("Get-Acl", text)
        self.assertIn("SIMBA_CORE_WINDOWS_PRIVATE_ACL_VERIFIED", text)
        self.assertIn("SIMBA_CORE_PRIVATE_DIR", text)
        self.assertNotIn("--execute-live", text)
        self.assertNotIn("--permit-billable-api-calls", text)
        self.assertNotIn("SIMBA_CORE_ALLOW_BILLABLE=1", text)
        self.assertNotIn("OPENAI_API_KEY=", text)

    def test_windows_setup_uses_zip_and_never_git_checkout(self):
        script = (ROOT / "plugins/simba-core/setup_simba_core_windows.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("recover_windows.py", script)
        self.assertIn("& $python.Source $helper", script)
        self.assertIn("Invoke-WebRequest -UseBasicParsing", script)
        self.assertIn("Custom RepoRoot is missing Simba CORE files", script)
        self.assertIn("if (-not $isDedicatedRepo)", script)
        self.assertNotIn("sparse-checkout", script)
        self.assertNotIn("clone --no-checkout", script)
        self.assertNotIn("archive --format=zip", script)
        self.assertNotIn("git checkout", script)
        self.assertNotIn("reset --hard", script)
        self.assertIn("Remove-Item -LiteralPath $helper -Force", script)

    def test_windows_setup_checks_windows_5_1_correctly(self):
        text = (ROOT / "plugins/simba-core/setup_simba_core_windows.ps1").read_text(encoding="utf-8")
        self.assertIn("[Environment]::OSVersion.Platform", text)
        self.assertNotIn("$IsWindows", text)
        self.assertIn("Test-Path -LiteralPath $server", text)
        self.assertIn("No API usage", text)

    def test_plugin_manifest_and_mcp_shape(self):
        plugin = json.loads((ROOT / "plugins/simba-core/plugin.json").read_text())
        config = json.loads((ROOT / "plugins/simba-core/mcp.json").read_text())
        self.assertTrue(plugin["extensions"]["com.openai"]["requires_local_executor"])
        server = config["mcpServers"]["simba-core"]
        self.assertEqual(server["type"], "stdio")
        self.assertIn("${PLUGIN_ROOT}", server["args"][0])


if __name__ == "__main__":
    unittest.main()
