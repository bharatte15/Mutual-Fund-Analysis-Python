"""Streamlit dashboard:  streamlit run app.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))  # run without `pip install -e .`

import numpy as np
import pandas as pd
import streamlit as st

from mfplan import data, metrics, optimization as opt, plots, portfolio as pf, simulation as sim
from mfplan.recommend import RISK_PROFILES, recommend_portfolio
from mfplan.report import build_report

st.set_page_config(page_title="Mutual Fund Planner", page_icon="📈", layout="wide")
st.title("📈 Mutual Fund Plan Builder")
st.caption("Educational tool - not investment advice.")


@st.cache_data(show_spinner="Loading fund data…")
def load(tickers: tuple, source: str, start: str, csv_bytes: bytes | None):
    csv_path = None
    if csv_bytes is not None:
        csv_path = "/tmp/uploaded_navs.csv"
        Path(csv_path).write_bytes(csv_bytes)
    return data.prepare(list(tickers), source=source, start=start, csv_path=csv_path)


@st.cache_data(show_spinner="Running Monte Carlo…")
def run_mc(port: pd.Series, years, initial, monthly, n_sims, method, seed):
    return sim.monte_carlo(port, years, initial, monthly, n_sims, method, seed)


# ------------------------------ sidebar inputs ------------------------------ #
with st.sidebar:
    st.header("1 · Data")
    source = st.selectbox("Data source", ["auto", "yahoo", "synthetic", "csv"],
                          help="auto = Yahoo Finance, falling back to synthetic demo data")
    csv_file = st.file_uploader("NAV CSV (Date + one column per fund)", type="csv") if source == "csv" else None
    tickers = st.multiselect("Funds", list(data.CATALOG), default=data.DEFAULT_FUNDS,
                             format_func=lambda t: f"{t} - {data.CATALOG[t].name}")
    start = st.date_input("History start", pd.Timestamp("2010-01-01")).isoformat()

    st.header("2 · Your plan")
    initial = st.number_input("Initial investment ($)", 0, 10_000_000, 10_000, 1_000)
    monthly = st.number_input("Monthly contribution ($)", 0, 100_000, 500, 50)
    years = st.slider("Time horizon (years)", 1, 40, 10)
    risk = st.select_slider("Risk tolerance", list(RISK_PROFILES), value="balanced")
    rf = st.slider("Risk-free rate (%)", 0.0, 8.0, 3.0, 0.25) / 100
    target = st.number_input("Goal amount ($, optional)", 0, 100_000_000, 0, 10_000)

    st.header("3 · Allocation")
    mode = st.radio("Mode", ["Recommended", "Optimised", "Custom"])
    n_sims = st.select_slider("Simulations", [1000, 2500, 5000, 10000], value=5000)
    method = st.radio("Simulation method", ["bootstrap", "parametric"], horizontal=True)
    rebalance = st.radio("Rebalancing", ["monthly", "none"], horizontal=True,
                         help="monthly = constant weights; none = buy-and-hold")

if len(tickers) < 2:
    st.warning("Select at least two funds in the sidebar.")
    st.stop()
if source == "csv" and csv_file is None:
    st.info("Upload a CSV to continue.")
    st.stop()

try:
    returns, bench, src = load(tuple(tickers), source, start, csv_file.getvalue() if csv_file else None)
except Exception as exc:
    st.error(f"Could not load data: {exc}")
    st.stop()

funds = list(returns.columns)
mu, cov = pf.annualized_mean_cov(returns)
if src == "synthetic":
    st.info("Showing **synthetic demo data** (offline). Choose *yahoo* for real fund history.")

# ------------------------------ allocation ---------------------------------- #
rationale = ""
if mode == "Recommended":
    rec = recommend_portfolio(returns, risk, years, rf)
    weights, rationale = rec.weights, rec.rationale
elif mode == "Optimised":
    goal = st.sidebar.radio("Objective", ["Max Sharpe", "Min variance"], horizontal=True)
    cap = st.sidebar.slider("Max weight per fund", 0.2, 1.0, 0.5, 0.05)
    cap = max(cap, 1 / len(funds) + 0.01)
    weights = opt.max_sharpe(mu, cov, rf, cap) if goal == "Max Sharpe" else opt.min_variance(mu, cov, cap)
    rationale = f"{goal} portfolio with a {cap:.0%} cap per fund."
else:
    raw = {t: st.sidebar.slider(t, 0, 100, int(100 / len(funds)), 5) for t in funds}
    if sum(raw.values()) == 0:
        st.warning("Give at least one fund a non-zero weight.")
        st.stop()
    weights = pf.normalize_weights(raw, funds)
    st.sidebar.caption(f"Weights are normalised to 100% (sum entered: {sum(raw.values())}).")

port = pf.portfolio_returns(returns, weights, rebalance)
perf = metrics.summarize(pd.concat([returns, port], axis=1), rf, data.expense_ratios(funds))
bench_perf = metrics.summarize(bench.rename("Benchmark").to_frame(), rf)
exp = pf.expected_performance(returns, weights, rf)
div = pf.diversification_report(returns, weights, data.categories(funds))
paths = run_mc(port, years, initial, monthly, n_sims, method, 0)
mc = sim.summarize_paths(paths, initial, monthly, target or None)

# ------------------------------ headline KPIs ------------------------------- #
c = st.columns(5)
p = perf.loc["Portfolio"]
c[0].metric("Annualized return", f"{p['Annualized return']:.1%}")
c[1].metric("Volatility", f"{p['Volatility']:.1%}")
c[2].metric("Sharpe", f"{p['Sharpe']:.2f}")
c[3].metric("Sortino", f"{p['Sortino']:.2f}")
c[4].metric("Max drawdown", f"{p['Max drawdown']:.1%}")

tabs = st.tabs(["Portfolio", "Fund explorer", "Risk & return", "Monte Carlo", "Sensitivity", "Report"])

with tabs[0]:
    l, r = st.columns([1, 2])
    l.plotly_chart(plots.allocation_pie(weights), use_container_width=True)
    r.plotly_chart(plots.growth_chart(port, bench, max(initial, 1)), use_container_width=True)
    for msg in div["warnings"]:
        st.warning(msg)
    if not div["warnings"]:
        st.success("No concentration warnings.")
    if rationale:
        st.caption(rationale)
    st.dataframe(pf.window_performance(port, rf=rf).style.format(
        {"Total return": "{:.1%}", "Annualized return": "{:.1%}", "Volatility": "{:.1%}",
         "Sharpe": "{:.2f}", "Max drawdown": "{:.1%}"}), use_container_width=True)
    st.plotly_chart(plots.drawdown_chart(port), use_container_width=True)

with tabs[1]:
    st.subheader("Fund statistics")
    st.dataframe(perf.drop(index="Portfolio").style.format("{:.3f}", na_rep="-"), use_container_width=True)
    a, b = st.columns(2)
    a.plotly_chart(plots.returns_heatmap(returns, port), use_container_width=True)
    b.plotly_chart(plots.correlation_heatmap(returns), use_container_width=True)
    pick = st.multiselect("Compare growth of $1", funds, default=funds[:3])
    if pick:
        st.line_chart(metrics.growth_of_one(returns[pick]))

with tabs[2]:
    frontier = opt.efficient_frontier(mu, cov, 30, max(0.5, 1 / len(funds) + 0.01))
    cloud = opt.random_portfolios(mu, cov, rf)
    fund_pts = pd.DataFrame({"Volatility": np.sqrt(np.diag(cov)), "Annualized return": mu.values}, index=funds)
    ms = opt.max_sharpe(mu, cov, rf)
    mv = opt.min_variance(mu, cov)
    special = {"Max Sharpe (unconstrained)": opt.portfolio_stats(ms.values, mu.values, cov.values, rf)[1::-1],
               "Min variance": opt.portfolio_stats(mv.values, mu.values, cov.values, rf)[1::-1]}
    st.plotly_chart(plots.risk_return_scatter(fund_pts, (exp["volatility"], exp["return"]), cloud, frontier,
                                              special), use_container_width=True)
    st.caption("Funds, frontier and portfolio use annualised arithmetic mean returns from monthly history.")

with tabs[3]:
    k = st.columns(4)
    pc = mc["percentiles"]
    k[0].metric("Contributed", f"${mc['invested']:,.0f}")
    k[1].metric("Median outcome", f"${pc['P50']:,.0f}")
    k[2].metric("Bad case (P5)", f"${pc['P5']:,.0f}")
    k[3].metric("Good case (P95)", f"${pc['P95']:,.0f}")
    st.write(f"Probability of ending below contributions: **{mc['prob_loss']:.1%}**"
             + (f" · probability of reaching ${target:,.0f}: **{mc['prob_target']:.1%}**" if target else ""))
    bands = sim.percentile_bands(paths)
    invested = pd.Series(initial + monthly * np.arange(len(bands)))
    st.plotly_chart(plots.fan_chart(bands, invested), use_container_width=True)
    st.plotly_chart(plots.final_value_hist(paths, mc["invested"]), use_container_width=True)

with tabs[4]:
    shift = st.slider("Shift size (percentage points)", 5, 25, 10, 5) / 100
    sens = pf.sensitivity_analysis(returns, weights, rf, shift)
    metric = st.radio("Metric", ["Δ Return", "Δ Volatility", "Δ Sharpe"], horizontal=True)
    st.plotly_chart(plots.sensitivity_chart(sens, metric), use_container_width=True)
    st.dataframe(sens.style.format({"New weight": "{:.0%}", "Δ Return": "{:+.2%}", "Δ Volatility": "{:+.2%}",
                                    "Δ Sharpe": "{:+.3f}"}), use_container_width=True)

with tabs[5]:
    cols = ["Annualized return", "Volatility", "Sharpe", "Sortino", "Max drawdown"]
    report = build_report(
        weights=weights, perf=perf.loc[funds + ["Portfolio"], cols], windows=pf.window_performance(port, rf=rf),
        div=div, mc=mc, benchmark_row=bench_perf[cols], rationale=rationale, data_source=src,
        params=dict(initial=initial, monthly=monthly, years=years, risk=risk, rf=rf))
    st.markdown(report)
    st.download_button("⬇️ Download report (.md)", report, "investment_plan.md", "text/markdown")
