"use strict";

function hasTable(db, table) {
  return Boolean(db.prepare(
    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
  ).get(table));
}

function tableColumns(db, table) {
  if (!hasTable(db, table)) return new Set();
  return new Set(db.prepare(`PRAGMA table_info(${table})`).all().map((row) => row.name));
}

function firstAvailable(columns, candidates) {
  return candidates.find((column) => columns.has(column)) || null;
}

function readSqlitePerformance(db) {
  const columns = tableColumns(db, "trades");
  if (columns.size === 0) {
    return {
      totalTrades: 0,
      openTrades: 0,
      closedTrades: 0,
      orders: hasTable(db, "orders")
        ? Number(db.prepare("SELECT COUNT(*) AS count FROM orders").get()?.count || 0)
        : 0,
      realizedProfit: null,
      totalProfit: null,
      totalProfitPercent: null,
      winrate: null,
      profitFactor: null,
      firstTradeDate: null,
      latestTradeDate: null,
      latestCloseDate: null,
    };
  }

  const isOpen = columns.has("is_open") ? "is_open" : null;
  const profitAbs = firstAvailable(columns, ["realized_profit", "close_profit_abs", "profit_abs"]);
  const profitRatio = firstAvailable(columns, ["close_profit", "realized_profit_ratio", "profit_ratio"]);
  const stakeAmount = columns.has("stake_amount") ? "stake_amount" : null;
  const openDate = columns.has("open_date") ? "open_date" : null;
  const closeDate = columns.has("close_date") ? "close_date" : null;
  const closedWhere = isOpen ? "WHERE is_open = 0" : "";
  const totalTrades = Number(db.prepare("SELECT COUNT(*) AS count FROM trades").get()?.count || 0);
  const openTrades = isOpen
    ? Number(db.prepare("SELECT COUNT(*) AS count FROM trades WHERE is_open = 1").get()?.count || 0)
    : 0;
  const closedTrades = isOpen ? totalTrades - openTrades : totalTrades;
  const aggregate = profitAbs
    ? db.prepare(`
      SELECT
        COALESCE(SUM(${profitAbs}), 0) AS realized_profit,
        COALESCE(SUM(CASE WHEN ${profitAbs} > 0 THEN ${profitAbs} ELSE 0 END), 0) AS gross_profit,
        COALESCE(SUM(CASE WHEN ${profitAbs} < 0 THEN ${profitAbs} ELSE 0 END), 0) AS gross_loss,
        COALESCE(SUM(CASE WHEN ${profitAbs} > 0 THEN 1 ELSE 0 END), 0) AS wins
        ${stakeAmount ? `, COALESCE(SUM(${stakeAmount}), 0) AS deployed_stake` : ""}
        ${profitRatio ? `, AVG(${profitRatio}) AS average_profit_ratio` : ""}
      FROM trades
      ${closedWhere}
    `).get()
    : null;

  const realizedProfit = aggregate ? Number(aggregate.realized_profit) : null;
  const deployedStake = aggregate && stakeAmount ? Number(aggregate.deployed_stake) : null;
  const totalProfitPercent = deployedStake && realizedProfit !== null
    ? (realizedProfit / deployedStake) * 100
    : (aggregate && profitRatio && aggregate.average_profit_ratio !== null
      ? Number(aggregate.average_profit_ratio) * 100
      : null);
  const grossProfit = aggregate ? Number(aggregate.gross_profit) : 0;
  const grossLoss = aggregate ? Math.abs(Number(aggregate.gross_loss)) : 0;

  return {
    totalTrades,
    openTrades,
    closedTrades,
    orders: hasTable(db, "orders")
      ? Number(db.prepare("SELECT COUNT(*) AS count FROM orders").get()?.count || 0)
      : 0,
    realizedProfit,
    totalProfit: realizedProfit,
    totalProfitPercent,
    winrate: closedTrades > 0 && aggregate ? Number(aggregate.wins) / closedTrades : null,
    profitFactor: grossLoss > 0 ? grossProfit / grossLoss : (grossProfit > 0 ? null : 0),
    firstTradeDate: openDate
      ? db.prepare(`SELECT MIN(${openDate}) AS value FROM trades`).get()?.value || null
      : null,
    latestTradeDate: openDate
      ? db.prepare(`SELECT MAX(${openDate}) AS value FROM trades`).get()?.value || null
      : null,
    latestCloseDate: closeDate
      ? db.prepare(`SELECT MAX(${closeDate}) AS value FROM trades ${closedWhere}`).get()?.value || null
      : null,
  };
}

module.exports = { firstAvailable, hasTable, readSqlitePerformance, tableColumns };
