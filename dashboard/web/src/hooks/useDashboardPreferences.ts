import { useCallback, useState } from "react";

export type DashboardVariant = "cockpit" | "terminal" | "narrative";
export type DashboardTheme = "dark" | "light";
export type ExpertiseMode = "guided" | "professional";
export type DensityMode = "comfortable" | "compact";
export type PreviewState = "live" | "loading" | "error" | "empty";

export interface DashboardPreferences {
  variant: DashboardVariant;
  theme: DashboardTheme;
  expertise: ExpertiseMode;
  density: DensityMode;
  previewState: PreviewState;
}

const STORAGE_KEY = "strategy-observatory:preferences:v1";
const DEFAULT_PREFERENCES: DashboardPreferences = {
  variant: "cockpit",
  theme: "dark",
  expertise: "guided",
  density: "comfortable",
  previewState: "live",
};

function isPreferences(value: unknown): value is DashboardPreferences {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<DashboardPreferences>;
  return new Set(["cockpit", "terminal", "narrative"]).has(candidate.variant || "")
    && new Set(["dark", "light"]).has(candidate.theme || "")
    && new Set(["guided", "professional"]).has(candidate.expertise || "")
    && new Set(["comfortable", "compact"]).has(candidate.density || "")
    && new Set(["live", "loading", "error", "empty"]).has(candidate.previewState || "");
}

function loadPreferences(): DashboardPreferences {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (!stored) return DEFAULT_PREFERENCES;
    const parsed: unknown = JSON.parse(stored);
    return isPreferences(parsed) ? parsed : DEFAULT_PREFERENCES;
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function savePreferences(preferences: DashboardPreferences): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  } catch {
    // Preferences are optional; private browsing or storage quotas must not block the dashboard.
  }
}

export function useDashboardPreferences() {
  const [preferences, setPreferencesState] = useState<DashboardPreferences>(loadPreferences);
  const setPreferences = useCallback((next: DashboardPreferences) => {
    setPreferencesState(next);
    savePreferences(next);
  }, []);
  const updatePreference = useCallback(<Key extends keyof DashboardPreferences>(
    key: Key,
    value: DashboardPreferences[Key],
  ) => {
    setPreferencesState((current) => {
      const next = { ...current, [key]: value };
      savePreferences(next);
      return next;
    });
  }, []);
  return { preferences, setPreferences, updatePreference };
}
