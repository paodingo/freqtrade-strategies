import json
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DryRunBotRuntimeTest(unittest.TestCase):
    def test_bot_runtime_is_digest_pinned_and_dry_run_reconciler_is_guarded(self):
        runtime = json.loads((ROOT / "deploy/runtime-bots.json").read_text(encoding="utf-8"))
        self.assertIn("@sha256:", runtime["image"])
        self.assertEqual({"freqtrade-v1129", "freqtrade-v1130-crash-rebound-shadow"}, {bot["name"] for bot in runtime["bots"]})
        reconciler = (ROOT / "deploy/reconcile_dry_run_bots.py").read_text(encoding="utf-8")
        self.assertIn("dry_run_only", reconciler)
        self.assertIn('config.get("dry_run") is not True', reconciler)
        self.assertIn("previous-", reconciler)
        self.assertIn("RestartCount", reconciler)

    def test_v1129_runtime_snapshot_has_closed_import_graph(self):
        root = ROOT / "runtime_snapshots/v1129/strategies"
        names = {path.stem for path in root.glob("*.py")}
        self.assertIn("RegimeAwareV1129ResidualDragMicroSizer", names)
        for path in root.glob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("tokens truncated", source)
            compile(source, str(path), "exec")
            for node in ast.walk(ast.parse(source)):
                dependencies = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    dependencies.append(node.module)
                elif isinstance(node, ast.Import):
                    dependencies.extend(alias.name for alias in node.names)
                for dependency in dependencies:
                    if (ROOT / "strategies" / f"{dependency}.py").is_file():
                        self.assertIn(dependency, names, f"{path.name} imports missing {dependency}")


if __name__ == "__main__":
    unittest.main()
