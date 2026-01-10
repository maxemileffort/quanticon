import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import os

def generate_html_report(engine, filename=None):
    """
    Generates a standalone HTML tearsheet for the backtest.
    """
    if filename is None:
        filename = f"backtests/{engine.strat_name}_report.html"
        
    # Ensure directory exists
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    # --- DATA PREP ---
    # Aggregate Portfolio Return
    strat_rets_dict = {}
    for ticker in engine.tickers:
        if ticker in engine.data and 'strategy_return' in engine.data[ticker].columns:
            strat_rets_dict[ticker] = engine.data[ticker]['strategy_return']
            
    if not strat_rets_dict:
        return
        
    all_returns = pd.DataFrame(strat_rets_dict).fillna(0)
    # Equal weight portfolio
    portfolio_log_returns = np.log1p((np.exp(all_returns) - 1).mean(axis=1))
    portfolio_cum = np.exp(portfolio_log_returns.cumsum())
    
    # Benchmark
    bench_cum = None
    if engine.benchmark_data is not None and not engine.benchmark_data.empty:
        bench_cum = np.exp(engine.benchmark_data['log_return'].cumsum())

    # --- PLOTS ---
    # 1. Equity Curve & Drawdown
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3],
                        subplot_titles=("Cumulative Returns", "Drawdown"))

    # Portfolio Line
    fig.add_trace(go.Scatter(x=portfolio_cum.index, y=portfolio_cum, name="Portfolio", 
                             line=dict(color='#00CC96', width=2)), row=1, col=1)
    
    # Benchmark Line
    if bench_cum is not None:
        # Align dates
        bench_cum = bench_cum.reindex(portfolio_cum.index).fillna(method='ffill')
        fig.add_trace(go.Scatter(x=bench_cum.index, y=bench_cum, name=f"Benchmark ({engine.benchmark_ticker})",
                                 line=dict(color='gray', dash='dash')), row=1, col=1)

    # Drawdown
    peak = portfolio_cum.cummax()
    dd = (portfolio_cum - peak) / peak
    fig.add_trace(go.Scatter(x=dd.index, y=dd, name="Drawdown", 
                             fill='tozeroy', line=dict(color='#EF553B')), row=2, col=1)

    fig.update_layout(template="plotly_white", height=600, title_text=f"Backtest Report: {engine.strat_name}")
    
    # 2. Monthly Returns Heatmap
    monthly_rets = portfolio_log_returns.resample('M').apply(lambda x: np.exp(x.sum()) - 1)
    monthly_rets_df = pd.DataFrame(monthly_rets)
    monthly_rets_df['Year'] = monthly_rets_df.index.year
    monthly_rets_df['Month'] = monthly_rets_df.index.month
    
    pivot_rets = monthly_rets_df.pivot(index='Year', columns='Month', values=0)
    # Rename columns to month names
    import calendar
    pivot_rets.columns = [calendar.month_abbr[i] for i in pivot_rets.columns]
    
    fig_heatmap = px.imshow(pivot_rets, 
                            labels=dict(x="Month", y="Year", color="Return"),
                            x=pivot_rets.columns,
                            y=pivot_rets.index,
                            color_continuous_scale="RdYlGn",
                            text_auto='.2%')
    fig_heatmap.update_layout(title="Monthly Returns", template="plotly_white")

    # --- HTML GENERATION ---
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>IvyBT Report - {engine.strat_name}</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 20px; background: #f4f4f4; }}
            .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
            h1, h2 {{ color: #333; }}
            .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }}
            .metric-card {{ background: #f9f9f9; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #eee; }}
            .metric-value {{ font-size: 24px; font-weight: bold; color: #00CC96; }}
            .metric-label {{ color: #666; font-size: 14px; }}
            .plot-container {{ margin-bottom: 30px; border: 1px solid #eee; padding: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>IvyBT Strategy Report</h1>
            <p><strong>Strategy:</strong> {engine.strat_name} | <strong>Range:</strong> {engine.start_date} to {engine.end_date}</p>
            
            <h2>Key Metrics (Portfolio)</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-value">{portfolio_cum.iloc[-1]-1:.2%}</div>
                    <div class="metric-label">Total Return</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{np.exp(portfolio_log_returns.mean()*252)-1:.2%}</div>
                    <div class="metric-label">Ann. Return</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{portfolio_log_returns.std()*np.sqrt(252):.2f}</div>
                    <div class="metric-label">Ann. Volatility</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{(np.exp(portfolio_log_returns.mean()*252)-1) / (portfolio_log_returns.std()*np.sqrt(252) + 1e-9):.2f}</div>
                    <div class="metric-label">Sharpe Ratio</div>
                </div>
                 <div class="metric-card">
                    <div class="metric-value">{dd.min():.2%}</div>
                    <div class="metric-label">Max Drawdown</div>
                </div>
            </div>

            <div class="plot-container">
                {fig.to_html(full_html=False, include_plotlyjs=False)}
            </div>
            
            <div class="plot-container">
                {fig_heatmap.to_html(full_html=False, include_plotlyjs=False)}
            </div>
        </div>
    </body>
    </html>
    """
    
    with open(filename, 'w') as f:
        f.write(html_content)
    
    return filename
