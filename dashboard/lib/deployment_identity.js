"use strict";

const fs = require("fs");
const path = require("path");

const SCHEMA_VERSION = "runtime-deployment-manifest-v1";

function unavailable(manifestFile, reason) {
  return {
    available: false,
    schema_version: SCHEMA_VERSION,
    release_id: null,
    git_sha: null,
    git_short_sha: null,
    environment: null,
    dry_run_only: null,
    built_at: null,
    deployed_at: null,
    manifest_file: manifestFile,
    status_reason: reason,
  };
}

function validateDeploymentManifest(document) {
  if (!document || document.schema_version !== SCHEMA_VERSION) {
    throw new Error("deployment_manifest_invalid:schema_version");
  }
  if (!/^[0-9a-f]{40}$/i.test(document.git_sha || "")) {
    throw new Error("deployment_manifest_invalid:git_sha");
  }
  if (document.dry_run_only !== true) {
    throw new Error("deployment_manifest_invalid:dry_run_only");
  }
  if (!Array.isArray(document.files) || document.files.length === 0) {
    throw new Error("deployment_manifest_invalid:files");
  }
  return document;
}

function loadDeploymentIdentity(projectDir, env = process.env) {
  const manifestFile = path.resolve(
    env.DEPLOYMENT_MANIFEST_FILE
      || path.join(projectDir, "user_data", "runtime-deployment-manifest.json"),
  );
  if (!fs.existsSync(manifestFile)) {
    return unavailable(manifestFile, "deployment_manifest_missing");
  }
  try {
    const document = validateDeploymentManifest(JSON.parse(fs.readFileSync(manifestFile, "utf8")));
    return {
      available: true,
      schema_version: document.schema_version,
      release_id: document.release_id,
      git_sha: document.git_sha,
      git_short_sha: document.git_sha.slice(0, 12),
      environment: document.environment,
      dry_run_only: document.dry_run_only,
      built_at: document.built_at,
      deployed_at: document.deployed_at || null,
      manifest_file: manifestFile,
      status_reason: null,
    };
  } catch (error) {
    return unavailable(
      manifestFile,
      error instanceof Error ? error.message : "deployment_manifest_invalid",
    );
  }
}

module.exports = {
  SCHEMA_VERSION,
  loadDeploymentIdentity,
  validateDeploymentManifest,
};
