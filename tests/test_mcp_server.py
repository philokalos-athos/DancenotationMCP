import unittest

from dancenotation_mcp.mcp_server.server import handle


class MCPServerTests(unittest.TestCase):
    def test_tools_list(self):
        resp = handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertIn("result", resp)
        names = [t["name"] for t in resp["result"]["tools"]]
        self.assertIn("plan_phrase", names)

    def test_plan_call(self):
        resp = handle(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "plan_phrase", "arguments": {"prompt": "step forward"}},
            }
        )
        self.assertIn("result", resp)
        payload = resp["result"]["content"][0]["json"]
        self.assertGreaterEqual(len(payload["steps"]), 1)


if __name__ == "__main__":
    unittest.main()
