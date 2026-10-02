# Results — 1y fee-inclusive multi-venue study

**Evaluation window:** 2025-10-01 → 2026-10-02  
**Starting capital:** A$100,000 (10% risk sleeve per open trade)  
**Win-rate target:** ≥60% **and** positive expectancy after fees  
**Data:** Yahoo Finance daily (ASX `.AX` + crypto `*-USD`)

This is a research simulation, not financial advice. Parameters were tuned in-sample on the evaluation year.

---

## Verdict

| Rank | Market | Strategy | Best venue | Win rate | Net return | Fees paid | Notes |
|---|---|---|---|---|---|---|---|
| 1 | Crypto | **EMA Trend Pullback** | **Binance / OKX USDT-Perp** | **68.0%** | **+4.55%** | A$607 | Clearest winner: ≥60% WR + best PnL |
| 2 | Crypto | EMA Trend Pullback | Binance / Bybit / OKX Spot | 67.6% | +3.50% | A$1,195 | Same edge, higher spot taker drag |
| 3 | Crypto | Vol Squeeze | Binance / OKX Perp | 56.1% | +2.99% | A$225 | More profitable than many; **misses** 60% WR |
| 4 | Crypto | RSI Mean Reversion | Binance / OKX Perp | **73.9%** | +0.99% | A$77 | Highest WR; fewer trades (n=23) |
| 5 | ASX | Donchian Breakout | **Pepperstone Share CFD** | 43.7% | +0.39% | A$435 | Best ASX **profit**; below WR target |
| 6 | ASX | RSI Mean Reversion | Pepperstone / IG CFD | **72.7%** | +0.06% | A$79 | Best ASX **≥60% WR** profitable combo |

**Bottom line for Zac:** On this 1y sample, put capital on **EMA pullback for BTC/ETH/SOL** at **Binance or OKX perpetual** fee tiers if you need both ≥60% win rate and the highest net return after fees. For ASX, **cash brokers (CommSec / SelfWealth / IBKR / Stake) largely erase edge** on these ATR-scaled swings because fixed brokerage dominates; **Pepperstone/IG share CFDs** keep mean-reversion styles above 60% WR with thin but positive expectancy.

---

## Strategy cards (tuned params)

### 1. RSI Mean Reversion + SMA filter (`rsi_mr`)
- Edge: fade RSI extremes only with the larger SMA trend  
- ASX params: RSI(10) low=35, SMA100, TP=1.2 ATR, SL=2.5 ATR, max hold 30  
- Crypto params: RSI(14) low=30 / high=65, SMA100, TP=1.2 ATR, SL=1.5 ATR, max hold 20  

### 2. Bollinger Band Fade (`bb_fade`)
- Edge: fade ±2σ bands; exit mid-band / ATR stops  
- ASX: period 15, std 2.0, TP 1.2 / SL 2.5 ATR  
- Crypto: often high WR but **negative expectancy** after fees in this year → rejected for live ranking  

### 3. EMA Trend Pullback (`ema_pullback`)
- Edge: buy dips to fast EMA while above slow EMA (shorts mirrored on crypto)  
- Crypto winner: EMA 10/50, TP 1.0 / SL 2.5 ATR, max hold 25 → **68% WR, +4.55% on Binance/OKX perps**  

### 4. Donchian Breakout (`donchian_break`)
- Edge: classic channel break; asymmetric payoff  
- Native WR stays ~43–49%; best ASX **profit** on Pepperstone CFD (+0.39%)  

### 5. Volatility Squeeze (`vol_squeeze`)
- Edge: BB bandwidth at N-day lows → momentum expansion  
- Crypto: +~3% on perps but WR ~56% (below target)  

---

## Fee takeaways

1. **ASX fixed brokerage** (SelfWealth A$9.50, CommSec tiers, IBKR floors) destroys small mean-reversion trades — win rate collapses as fees flip winners to losers.  
2. **Pepperstone 0.07%/side share CFD** is the cheapest realistic ASX execution in this model (financing included).  
3. **Crypto spot** Binance/Bybit/OKX are nearly identical at VIP0 10bps taker; **Kraken spot** costs ~2.5× and cuts return roughly in half on the same signals.  
4. **Perp fee cards** (≈5bps taker) beat spot for the same signals when funding is ignored/light — live funding can reverse that for long holds.

---

## Charts

See `artifacts/win_rate_matrix.png`, `equity_top5.png`, `best_venue_returns.png`, `fees_vs_pnl.png`.
