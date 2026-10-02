# AU + Crypto Strategy Backtest Study

Research package that designs five professional daily strategies, tunes them for ~≥60% win rate **with positive expectancy**, and compares fee-inclusive 1-year results across Australian brokers and major crypto venues.

## Quick start

```bash
cd research/au_crypto_strategies
/workspace/.venv/bin/python run_study.py
```

Outputs land in `artifacts/`:

- `summary.csv` — every strategy × venue metric
- `winrate_ge_60.csv` — combos hitting the win-rate target
- `REPORT.md` — ranked leaders
- Charts: `win_rate_matrix.png`, `equity_top5.png`, `best_venue_returns.png`, `fees_vs_pnl.png`

## Strategies

| ID | Name |
|---|---|
| `rsi_mr` | RSI mean reversion + SMA regime filter |
| `bb_fade` | Bollinger band fade |
| `ema_pullback` | EMA trend pullback |
| `donchian_break` | Donchian channel breakout |
| `vol_squeeze` | Volatility squeeze → momentum |

See `RESEARCH.md` for fee schedules, methodology, and caveats.

## Not financial advice

Backtests are simulated; past results do not guarantee future performance.
