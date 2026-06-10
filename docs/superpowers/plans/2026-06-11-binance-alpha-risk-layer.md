# Binance Alpha Risk Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only Binance USD-M futures intelligence layer that scores BTC contract crowding and risk before it affects strategy execution.

**Architecture:** Create a focused dashboard library for Binance futures fetching, normalization, short-lived caching, and risk scoring. Expose it through `/api/alpha-risk` and render it in the dashboard as an observation panel only.

**Tech Stack:** Node.js dashboard server, Binance public REST endpoints, static HTML/CSS/JS dashboard, `node:test`.

---

### Task 1: Contract Intelligence Module

**Files:**
- Create: `dashboard/lib/binance_futures_alpha.js`
- Test: `tests/test_binance_futures_alpha.js`

- [ ] **Step 1: Write failing tests**

Add tests that require `buildBinanceFuturesAlphaSnapshot`, `classifyAlphaRisk`, and `BINANCE_FUTURES_ALPHA_ENDPOINTS`. Verify that the endpoint map includes `/fapi/v1/premiumIndex`, `/fapi/v1/fundingRate`, `/futures/data/openInterestHist`, `/futures/data/globalLongShortAccountRatio`, `/futures/data/topLongShortPositionRatio`, `/futures/data/topLongShortAccountRatio`, and `/futures/data/takerlongshortRatio`. Verify that crowded long fixtures produce at least a warning risk level and neutral fixtures stay neutral or good.

- [ ] **Step 2: Run the test red**

Run: `node --test tests/test_binance_futures_alpha.js`

Expected: FAIL because `dashboard/lib/binance_futures_alpha.js` does not exist.

- [ ] **Step 3: Implement the module**

Create functions that parse Binance numeric strings, select the newest sample from array endpoints, calculate funding percent, OI 15m change, long/short crowding, taker buy share, premium percent, and a simple additive risk score. Export a `createBinanceFuturesAlphaFetcher` function that uses `fetch`, caches snapshots briefly, and degrades to partial data when one endpoint fails.

- [ ] **Step 4: Run the test green**

Run: `node --test tests/test_binance_futures_alpha.js`

Expected: PASS.

### Task 2: API Wiring

**Files:**
- Modify: `dashboard/server.js`
- Modify: `dashboard/lib/config.js`
- Test: `tests/test_dashboard_public_metadata.js`

- [ ] **Step 1: Write failing static coverage**

Extend dashboard metadata tests to require `/api/alpha-risk`, `handleApiAlphaRisk`, `createBinanceFuturesAlphaFetcher`, `state.alphaRisk`, and `fetchJson("/api/alpha-risk")`.

- [ ] **Step 2: Run the test red**

Run: `node --test tests/test_dashboard_public_metadata.js`

Expected: FAIL because API and frontend wiring are missing.

- [ ] **Step 3: Implement API wiring**

Import `createBinanceFuturesAlphaFetcher`, configure cache TTL and period from environment, instantiate one fetcher, and serve `/api/alpha-risk`.

- [ ] **Step 4: Run the test green**

Run: `node --test tests/test_dashboard_public_metadata.js`

Expected: PASS.

### Task 3: Dashboard Panel

**Files:**
- Modify: `dashboard/public/index.html`
- Modify: `dashboard/public/app.js`
- Modify: `dashboard/public/styles.css`

- [ ] **Step 1: Add UI containers**

Add a `contractIntelPanel` section with `alphaRiskTitle`, `alphaRiskSummary`, and `alphaRiskGrid`.

- [ ] **Step 2: Render intelligence**

Fetch `/api/alpha-risk` with each refresh, store it on `state.alphaRisk`, and render funding, OI change, global long/short, top trader position, taker flow, and mark/index premium.

- [ ] **Step 3: Style without changing layout fundamentals**

Use existing panel/card patterns with restrained status colors.

### Task 4: Verification and Deployment

**Files:**
- No new source files beyond Tasks 1-3.

- [ ] **Step 1: Local checks**

Run: `node --check dashboard/server.js`, `node --check dashboard/public/app.js`, `node --test tests/test_binance_futures_alpha.js tests/test_dashboard_public_metadata.js tests/test_dashboard_interpretation.js tests/test_monitor_store.js`.

- [ ] **Step 2: Commit and push**

Commit message: `Add Binance futures alpha risk layer`.

- [ ] **Step 3: Deploy to server**

Run: `ssh -i D:/key/openclaw/clf.pem ubuntu@43.134.72.69 'cd /home/ubuntu/freqtrade-strategies && git pull --ff-only && sudo systemctl restart freqtrade-monitor.service && sleep 2 && git rev-parse --short HEAD && systemctl is-active freqtrade-monitor.service'`

- [ ] **Step 4: Server verification**

Call `http://localhost:8090/api/alpha-risk` on the server with dashboard credentials and confirm it returns `symbol`, `risk`, `metrics`, and `signals`.
