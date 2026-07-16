import "@fontsource-variable/jetbrains-mono";
import "@fontsource-variable/sora";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { App } from "./App";
import "./styles.css";
import "./data-panels.css";
import "./views.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      gcTime: 5 * 60_000,
      refetchOnReconnect: true,
    },
  },
});

const root = document.getElementById("root");
if (!root) throw new Error("dashboard_root_missing");

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
