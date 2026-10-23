# 📈 Mutual Fund Planner

Build, simulate and optimise a diversified mutual fund investment plan in Python.
Pick funds, set your amount / horizon / risk tolerance, and get a recommended allocation,
historical risk metrics, a Monte Carlo outlook, an efficient-frontier view and a downloadable report -
through an interactive **Streamlit dashboard** or a one-line **CLI**.

> ⚠️ Educational project - **not investment advice**. Historical results do not predict the future.
> Fund expense ratios in `data.py` are approximate; check current figures before relying on them.

![Growth](docs/images/growth.png)

## Features

| Area | What it does |
|---|---|
| **Data** | Yahoo Finance (`yfinance`), your own CSV, or an offline seeded simulator (auto-fallback). Cleans gaps/duplicates/bad prices, resamples to monthly, winsorises outliers (robust MAD). |
| **Metrics** | Total & annualised return, volatility, Sharpe, Sortino, max drawdown, expense ratio, calendar-year returns. |
| **Portfolio** | Custom weights, monthly-rebalanced or buy-and-hold, diversification checks (concentration, effective # of funds, correlation), trailing-window "what if I'd started N years ago" scenarios. |
| **Simulation** | Monte Carlo (bootstrap or parametric) with monthly contributions, percentile fan chart, probability of loss / hitting a goal. |
| **Optimisation** | Min-variance, max-Sharpe, efficient frontier (SciPy SLSQP, long-only, per-fund cap). |
| **Recommendation** | Conservative / balanced / aggressive → a point on the efficient frontier, adjusted for horizon. |
| **Sensitivity** | Impact on return / risk / Sharpe of shifting ±N points into each fund. |
| **Output** | Interactive Plotly dashboard, PNG charts, Markdown report. |

<p align="center">
  <img src="docs/images/risk_return.png" width="48%">
  <img src="docs/images/monte_carlo.png" width="48%">
</p>
<p align="center">
  <img src="docs/images/allocation.png" width="30%">
  <img src="docs/images/heatmap.png" width="65%">
</p>

*(Images above were generated from the built-in synthetic demo data - see `docs/images/report.md` for the matching report.)*

## Quick start

```bash
git clone https://github.com/<your-username>/mutual-fund-planner.git
cd mutual-fund-planner
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt && pip install -e .

streamlit run app.py                                    # interactive dashboard
mfplan --risk balanced --years 10 --monthly 500 --out reports   # CLI report + charts
```

No internet? Use `--source synthetic` (CLI) or pick *synthetic* in the dashboard.
Bring your own data: `mfplan --source csv --csv data/sample_navs.csv --funds VFIAX,VSMAX,VTIAX,VGSLX,VBTLX`
(CSV format: `Date` column, one NAV column per fund, optional `^SP500TR` benchmark column - see `data/sample_navs.csv`).

### Use as a library

```python
from mfplan import data, portfolio as pf, simulation as sim
from mfplan.recommend import recommend_portfolio

returns, bench, src = data.prepare(["VFIAX", "VBTLX", "VTIAX"], source="auto")
rec = recommend_portfolio(returns, "balanced", horizon_years=15, rf=0.03)
port = pf.portfolio_returns(returns, rec.weights)
paths = sim.monte_carlo(port, years=15, initial=10_000, monthly_contribution=500)
print(rec.weights.round(2), sim.summarize_paths(paths, 10_000, 500)["percentiles"])
```

## Project layout

```
app.py                 Streamlit dashboard
src/mfplan/
  data.py              sources, cleaning, feature engineering, fund catalogue
  metrics.py           return / risk metrics
  portfolio.py         weights, diversification, scenarios, sensitivity
  simulation.py        Monte Carlo
  optimization.py      min-variance, max-Sharpe, efficient frontier
  recommend.py         risk-profile recommendation
  report.py            Markdown report
  plots.py             Plotly charts (dashboard)
  static_plots.py      Matplotlib charts (CLI / README)
  cli.py               `mfplan` command
tests/                 pytest suite (metrics, data, portfolio, simulation, optimisation, CLI)
data/sample_navs.csv   example input file
```

## Methodology notes

* **Returns** are monthly, net of expenses (adjusted close includes dividends). Annualised return = CAGR; the optimiser and expected-return figures use annualised *arithmetic* mean × 12 and covariance × 12, so the efficient-frontier plot uses those for funds too.
* **Sharpe** = mean excess return / std of excess return × √12. **Sortino** uses downside deviation below the risk-free rate.
* **Monte Carlo (bootstrap)** resamples historical monthly portfolio returns (keeps fat tails; assumes months are independent). Contributions arrive at month end. "Probability of loss" = ending below total money contributed.
* **Recommendation**: min-variance → max-return frontier position of 0 / 0.5 / 0.9 for conservative / balanced / aggressive; <5-year horizons halve it, ≥15-year horizons add 0.1. Per-fund cap defaults to 50 %.
* **Limitations**: mean-variance optimisation is sensitive to noisy return estimates and tends to concentrate; no taxes, fees beyond expense ratios, or inflation; synthetic data is illustrative only.

## Development

```bash
pip install -r requirements-dev.txt && pip install -e .
pytest -q && ruff check .
```

CI (GitHub Actions) runs lint + tests on Python 3.10-3.12.

## Roadmap ideas
Black-Litterman / shrinkage covariance · inflation-adjusted & tax-aware simulation · goal-based glide paths · SIP/lump-sum comparison · more fund universes (e.g. Indian AMFI NAVs).

## License
MIT - see [LICENSE](LICENSE).
