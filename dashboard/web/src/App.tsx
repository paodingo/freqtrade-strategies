import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchStrategyRegistry } from "./api/strategyRegistry";
import { DashboardHeader } from "./components/DashboardHeader";
import { StatePanel } from "./components/StatePanel";
import { TweaksPanel } from "./components/TweaksPanel";
import { useDashboardPreferences } from "./hooks/useDashboardPreferences";
import { CockpitView } from "./variants/CockpitView";
import { NarrativeView } from "./variants/NarrativeView";
import { TerminalView } from "./variants/TerminalView";

export function App() {
  const [tweaksOpen, setTweaksOpen] = useState(false);
  const { preferences, updatePreference } = useDashboardPreferences();
  const registryQuery = useQuery({
    queryKey: ["strategy-registry", "v1"],
    queryFn: ({ signal }) => fetchStrategyRegistry(signal),
    staleTime: 4_000,
    refetchInterval: 5_000,
    refetchOnWindowFocus: true,
    retry: 1,
  });

  useEffect(() => {
    document.documentElement.dataset.theme = preferences.theme;
    document.documentElement.dataset.density = preferences.density;
    document.documentElement.dataset.variant = preferences.variant;
  }, [preferences.density, preferences.theme, preferences.variant]);

  useEffect(() => {
    if (!tweaksOpen) return undefined;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setTweaksOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [tweaksOpen]);

  const retryLiveData = () => {
    updatePreference("previewState", "live");
    void registryQuery.refetch();
  };

  const forcedState = preferences.previewState;
  const showLoading = forcedState === "loading" || (forcedState === "live" && registryQuery.isPending);
  const showError = forcedState === "error" || (forcedState === "live" && registryQuery.isError);
  const showEmpty = forcedState === "empty"
    || (forcedState === "live" && registryQuery.isSuccess && registryQuery.data.strategies.length === 0);
  const data = registryQuery.data;

  return (
    <div className="app-shell">
      <DashboardHeader
        data={data}
        expertise={preferences.expertise}
        isFetching={registryQuery.isFetching}
        onExpertiseChange={(mode) => updatePreference("expertise", mode)}
      />

      {showLoading ? <StatePanel state="loading" /> : null}
      {showError ? <StatePanel state="error" onRetry={retryLiveData} /> : null}
      {showEmpty ? <StatePanel state="empty" /> : null}

      {!showLoading && !showError && !showEmpty && data ? (
        <>
          {preferences.variant === "cockpit" ? (
            <CockpitView data={data} expertise={preferences.expertise} />
          ) : null}
          {preferences.variant === "terminal" ? (
            <TerminalView data={data} expertise={preferences.expertise} />
          ) : null}
          {preferences.variant === "narrative" ? (
            <NarrativeView data={data} expertise={preferences.expertise} />
          ) : null}
        </>
      ) : null}

      <button
        className="tweaks-trigger"
        type="button"
        aria-expanded={tweaksOpen}
        aria-controls="tweaks-panel"
        onClick={() => setTweaksOpen((open) => !open)}
      >
        <span aria-hidden="true">V0</span>
        调整界面
      </button>
      <div id="tweaks-panel">
        <TweaksPanel
          open={tweaksOpen}
          preferences={preferences}
          onClose={() => setTweaksOpen(false)}
          onUpdate={updatePreference}
        />
      </div>
    </div>
  );
}
