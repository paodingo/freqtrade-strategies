import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseBundleTest(unittest.TestCase):
    def test_bundle_is_built_from_git_and_is_dry_run_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp) / "release.tgz"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/build_release_bundle.py"),
                    "--repo",
                    str(ROOT),
                    "--ref",
                    "HEAD",
                    "--output",
                    str(bundle),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            with tarfile.open(bundle, "r:gz") as archive:
                names = archive.getnames()
                manifest = json.load(archive.extractfile("runtime-deployment-manifest.json"))
            self.assertTrue(manifest["dry_run_only"])
            self.assertRegex(manifest["git_sha"], r"^[0-9a-f]{40}$")
            self.assertIn("dashboard/server.js", names)
            self.assertIn("scripts/notify_trades.sh", names)
            self.assertIn("scripts/data_reliability_controller.py", names)
            self.assertIn("deploy/freqtrade-data-reliability.service", names)
            self.assertIn("deploy/freqtrade-data-reliability.timer", names)
            self.assertNotIn("user_data/monitor.env", names)


if __name__ == "__main__":
    unittest.main()
