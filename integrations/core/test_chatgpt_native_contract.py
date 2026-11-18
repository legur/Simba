"""Offline structural checks for CHATGPT_NATIVE_EDITORIAL runtime invariants.

These tests prove policy references and guardrails, NOT that a live ChatGPT
assistant executed independent author/Critic/Humanizer tools.
"""
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CANON = "SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/CHATGPT_NATIVE_EDITORIAL.md"
SOURCES = (
    "AGENTS.md",
    "ROUTER_v10.1.md",
    "META-Governance-v8.1.md",
    "SIMBA KNOWLEDGE BASE/00_CORE/KNOWLEDGE_MAP.md",
    "SIMBA KNOWLEDGE BASE/00_CORE/KB_RUNTIME_PROTOCOL.md",
    "SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/CONTENT_PIPELINE.md",
    "SIMBA KNOWLEDGE BASE/06_AGENT_WORKFLOWS/AGENT_ROLES.md",
    "plugins/simba-core/skills/simba-editorial/SKILL.md",
)


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8-sig")


class ChatGPTNativeContractTest(unittest.TestCase):
    def test_new_canon_exists_and_referenced_by_every_owner(self):
        canon = read(CANON)
        self.assertIn("CHAT_NATIVE_SINGLE_MODEL", canon)
        self.assertIn("CHAT_NATIVE_VERIFIED_ROLE_TOOLS", canon)
        self.assertIn("CHAT_DRAFT_SELF_REVIEWED_INDEPENDENCE_UNVERIFIED", canon)
        self.assertIn("BLOCKED_INDEPENDENT_EXECUTOR_UNAVAILABLE", canon)
        for path in SOURCES:
            with self.subTest(path=path):
                self.assertIn("CHATGPT_NATIVE_EDITORIAL.md", read(path))

    def test_single_model_draft_never_claims_independent_agent_pass(self):
        canon = read(CANON)
        scope = canon.split("### A. `CHAT_NATIVE_SINGLE_MODEL`", 1)[-1].split(
            "### B. `CHAT_NATIVE_VERIFIED_ROLE_TOOLS`", 1
        )[0]
        for value in ("не три", "INTERNAL_CRITIC_PASS", "HUMANIZER_PASS",
                      "APPROVED_TEXT", "PUBLISHED"):
            with self.subTest(value=value):
                self.assertIn(value, scope)
        self.assertIn("CHAT_DRAFT_SELF_REVIEWED_INDEPENDENCE_UNVERIFIED", scope)

    def test_real_tools_have_exact_revision_evidence(self):
        canon = read(CANON)
        scope = canon.split("### B. `CHAT_NATIVE_VERIFIED_ROLE_TOOLS`", 1)[-1]
        for marker in ("SHA-256", "output", "tool", "фактические", "APPROVED_TEXT"):
            self.assertIn(marker, scope)

    def test_local_mcp_and_api_are_optional(self):
        manifest = json.loads(read("plugins/simba-core/plugin.json"))
        self.assertFalse(manifest["extensions"]["com.openai"]["requires_local_executor"])
        skill = read("plugins/simba-core/skills/simba-editorial/SKILL.md")
        self.assertIn("локального MCP", skill)
        self.assertIn("без", skill.lower())
        self.assertIn("ChatGPT", skill)
        self.assertIn("simba_core_run_private_pilot", skill)
        self.assertIn("explicit budget opt-in", skill)

    def test_no_misleading_production_claims_or_video_scope(self):
        canon = read(CANON)
        self.assertIn("OFFLINE_HANDOFF_CONTRACT_OK_NOT_AGENT_EXECUTION", canon)
        self.assertIn("leo", canon.lower())
        self.assertIn("source", canon.lower())
        self.assertIn("TIA", canon)
        self.assertIn("Киностудия", canon)
        self.assertIn("publication", read("plugins/simba-core/plugin.json"))


if __name__ == "__main__":
    unittest.main()
