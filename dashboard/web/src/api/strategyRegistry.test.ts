import { describe, expect, it } from "vitest";

import { assertStrategyRegistryResponse } from "./strategyRegistry";

function registryResponse(role: "current" | "shadow" = "current") {
  return {
    schema_version: "strategy-registry-response-v1",
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
});
