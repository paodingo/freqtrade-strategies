import { describe, expect, it } from "vitest";

import { assertStrategyRegistryResponse } from "./strategyRegistry";

function registryResponse(role: "current" | "shadow" = "current") {
  return {
    schema_version: "strategy-registry-response-v1",
    data_reliability: {
      schema_version: "data-reliability-report-v1",
      decision_allowed: true,
      summary: { check_count: 1, reliable_count: 1, issue_count: 0, blocking_count: 0 },
      issues: [],
    },
    strategies: [{ role }],
  };
}

describe("assertStrategyRegistryResponse", () => {
  it("accepts one current strategy", () => {
    expect(() => assertStrategyRegistryResponse(registryResponse())).not.toThrow();
  });

  it("rejects a non-empty registry without one current strategy", () => {
    expect(() => assertStrategyRegistryResponse(registryResponse("shadow"))).toThrow(
      "strategy_registry_response_invalid:current_role_count:0",
    );
  });

  it("rejects an unexpected response contract", () => {
    expect(() => assertStrategyRegistryResponse({ schema_version: "legacy", strategies: [] })).toThrow(
      "strategy_registry_response_invalid:schema_version",
    );
  });

  it("rejects a response without a reliability decision", () => {
    const response = registryResponse();
    response.data_reliability.decision_allowed = undefined as never;
    expect(() => assertStrategyRegistryResponse(response)).toThrow(
      "strategy_registry_response_invalid:data_reliability_decision",
    );
  });
});
