"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  loadDeploymentIdentity,
  validateDeploymentManifest,
} = require("../dashboard/lib/deployment_identity");

function manifest() {
  return {
    schema_version: "runtime-deployment-manifest-v1",
    release_id: "dry-run-0123456789ab",
    git_sha: "0123456789abcdef0123456789abcdef01234567",
    environment: "cloud-dry-run",
    dry_run_only: true,
    built_at: "2026-07-18T00:00:00Z",
    files: [{ path: "dashboard/server.js", sha256: "a".repeat(64), size: 1 }],
  };
}

test("deployment identity exposes immutable release SHA", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "deployment-identity-"));
  const file = path.join(dir, "manifest.json");
  fs.writeFileSync(file, JSON.stringify(manifest()));
  const identity = loadDeploymentIdentity(dir, { DEPLOYMENT_MANIFEST_FILE: file });
  assert.equal(identity.available, true);
  assert.equal(identity.git_short_sha, "0123456789ab");
  assert.equal(identity.dry_run_only, true);
});

test("deployment manifest rejects any non-dry-run release", () => {
  const document = manifest();
  document.dry_run_only = false;
  assert.throws(() => validateDeploymentManifest(document), /dry_run_only/);
});
