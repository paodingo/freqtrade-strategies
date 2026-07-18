import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_git_lifecycle.py"
SPEC = importlib.util.spec_from_file_location("audit_git_lifecycle", SCRIPT)
LIFECYCLE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(LIFECYCLE)


def run_git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


class GitLifecycleTest(unittest.TestCase):
    def test_only_merged_unprotected_unchecked_branch_is_cleanup_eligible(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            run_git(repo.parent, "init", "-b", "master", str(repo))
            run_git(repo, "config", "user.email", "test@example.com")
            run_git(repo, "config", "user.name", "Test")
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            run_git(repo, "add", "README.md")
            run_git(repo, "commit", "-m", "base")
            run_git(repo, "branch", "merged-topic")
            run_git(repo, "switch", "-c", "unmerged-topic")
            (repo / "topic.txt").write_text("topic\n", encoding="utf-8")
            run_git(repo, "add", "topic.txt")
            run_git(repo, "commit", "-m", "topic")
            run_git(repo, "switch", "master")
            policy = {
                "base_branch": "master", "protected_branches": ["master"],
                "protected_prefixes": [], "max_local_branches": 8, "max_worktrees": 5,
            }
            report = LIFECYCLE.build_report(policy, repo)
        by_name = {branch["name"]: branch for branch in report["branches"]}
        self.assertTrue(by_name["merged-topic"]["cleanup_eligible"])
        self.assertFalse(by_name["unmerged-topic"]["cleanup_eligible"])
        self.assertFalse(by_name["master"]["cleanup_eligible"])

    def test_policy_is_safe_by_default(self):
        policy = json.loads((ROOT / "harness/lifecycle-policy.json").read_text(encoding="utf-8"))
        self.assertIn("master", policy["protected_branches"])
        self.assertGreaterEqual(policy["max_worktrees"], 1)


if __name__ == "__main__":
    unittest.main()
