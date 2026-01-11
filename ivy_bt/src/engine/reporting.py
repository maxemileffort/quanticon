import pandas as pd
import numpy as np
import logging
import os
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

class ReportingMixin:
    def generate_report(self):
        """Generates a professional comparison tearsheet with Position Size."""
        # 1. Intersect results with self.tickers + always include the benchmark
        active_results = {
            k: v for k, v in self.results.items()
            if k in self.tickers or k.startswith("BENCHMARK")
        }

        # 2. Convert to DataFrame for display
        summary_df = pd.DataFrame(active_results).T
        logging.info("\n" + str(summary_df))

        # Plotting
        fig, axes = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
        sns.set_style("darkgrid")
        
        # Top: Equity Curves
        ax0 = axes[0]
        for ticker in self.tickers:
            if ticker in self.data:
                strat_cum = np.exp(self.data[ticker]['strategy_return'].cumsum())
                ax0.plot(strat_cum, label=f"Strategy: {ticker} / {self.strat_name}", linewidth=2)

        # Plot Benchmark Equity Curve
        bench_cum = np.exp(self.benchmark_data['log_return'].cumsum())
        ax0.plot(bench_cum, label=f"Benchmark: {self.benchmark_ticker}",
                 color='black', linestyle='--', alpha=0.7, linewidth=3)

        ax0.set_title(f"Cumulative Performance vs {self.benchmark_ticker}", fontsize=16)
        ax0.set_ylabel("Growth of $1")
        ax0.legend()

        # Bottom: Position Sizes
        ax1 = axes[1]
        for ticker in self.tickers:
            if ticker in self.data and 'position_size' in self.data[ticker]:
                ax1.plot(self.data[ticker]['position_size'], label=f"{ticker} Size")
        
        ax1.set_title("Position Size / Leverage Over Time")
        ax1.set_ylabel("Size")
        ax1.legend()

        plt.tight_layout()
        plt.show()

    def generate_portfolio_report(self):
        """Aggregates all tickers into one portfolio equity curve."""
        # 1. Pull the actual strategy return columns from self.data
        strat_rets_dict = {}
        for ticker in self.tickers:
            if 'strategy_return' in self.data[ticker].columns:
                strat_rets_dict[ticker] = self.data[ticker]['strategy_return']

        all_returns = pd.DataFrame(strat_rets_dict).fillna(0)

        # 2. Calculate Portfolio Returns (Equal Weighted)
        # We use mean across columns, then convert log returns to simple returns for the visual
        all_simple_returns = np.exp(all_returns) - 1
        portfolio_simple_returns = all_simple_returns.mean(axis=1)
        portfolio_log_returns = np.log1p(portfolio_simple_returns)
        
        portfolio_cum_growth = np.exp(portfolio_log_returns.cumsum())

        # 3. Portfolio Metrics
        port_total_ret = portfolio_cum_growth.iloc[-1] - 1
        port_ann_ret = np.exp(portfolio_log_returns.mean() * self.annualization_factor) - 1
        port_ann_vol = portfolio_log_returns.std() * np.sqrt(self.annualization_factor)
        port_sharpe = port_ann_ret / port_ann_vol if port_ann_vol != 0 else 0

        logging.info(f"\n=== AGGREGATE PORTFOLIO REPORT: {self.strat_name} ===")
        logging.info(f"Total Tickers: {len(self.tickers)}")
        logging.info(f"Portfolio Total Return: {port_total_ret:.2%}")
        logging.info(f"Portfolio Sharpe Ratio: {port_sharpe:.2f}")

        # 4. Visualizing Portfolio vs Benchmark

        plt.figure(figsize=(14, 7))
        sns.set_style("whitegrid")

        plt.plot(portfolio_cum_growth, label='Total Portfolio (Equal Weighted)', color='gold', linewidth=3)

        bench_cum = np.exp(self.benchmark_data['log_return'].cumsum())
        plt.plot(bench_cum, label=f'Benchmark ({self.benchmark_ticker})', color='black', linestyle='--', alpha=0.6)

        plt.title(f"Portfolio Cumulative Performance - {self.strat_name}", fontsize=16)
        plt.ylabel("Growth of $1 (Log Scale Basis)")
        plt.legend()
        plt.show()

    def generate_pdf_report(self, filename=None):
        """
        Generates a PDF tearsheet using Matplotlib.
        """
        if filename is None:
            filename = f"backtests/{self.strat_name}_report.pdf"
            
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Data Prep
        portfolio_log_returns = self.get_portfolio_returns()
        if portfolio_log_returns.empty:
            return

        portfolio_cum = np.exp(portfolio_log_returns.cumsum())
        
        # Benchmark
        bench_cum = None
        if self.benchmark_data is not None and not self.benchmark_data.empty:
            bench_cum = np.exp(self.benchmark_data['log_return'].cumsum())
            # Align
            bench_cum = bench_cum.reindex(portfolio_cum.index).fillna(method='ffill')

        # Metrics
        metrics = self.calculate_risk_metrics(portfolio_log_returns)
        total_ret = portfolio_cum.iloc[-1] - 1
        
        with PdfPages(filename) as pdf:
            # --- Page 1: Overview & Equity Curve ---
            fig1 = plt.figure(figsize=(11, 8.5))
            plt.suptitle(f"IvyBT Report: {self.strat_name}", fontsize=16, weight='bold')
            
            # Text Metrics
            txt = f"Range: {self.start_date} to {self.end_date}\n"
            txt += f"Total Return: {total_ret:.2%}\n"
            if metrics:
                txt += f"Sharpe Ratio: {metrics.get('Sharpe Ratio', 'N/A')}\n"
                txt += f"Max Drawdown: {metrics.get('Max Drawdown', 'N/A')}\n"
                txt += f"VaR (95%): {metrics.get('VaR (95%)', 'N/A')}\n"
                txt += f"Sortino: {metrics.get('Sortino Ratio', 'N/A')}"
                
            plt.figtext(0.1, 0.9, txt, fontsize=12, va="top")
            
            # Equity Curve
            ax1 = plt.subplot2grid((3, 1), (1, 0), rowspan=2)
            ax1.plot(portfolio_cum.index, portfolio_cum.values, label='Portfolio', color='blue')
            if bench_cum is not None:
                ax1.plot(bench_cum.index, bench_cum.values, label=f'Benchmark ({self.benchmark_ticker})', color='gray', linestyle='--')
            
            ax1.set_title("Cumulative Growth of $1")
            ax1.set_ylabel("Growth")
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            pdf.savefig(fig1)
            plt.close()
            
            # --- Page 2: Drawdown & Volatility ---
            fig2 = plt.figure(figsize=(11, 8.5))
            
            # Drawdown
            peak = portfolio_cum.cummax()
            dd = (portfolio_cum - peak) / peak
            
            ax2 = plt.subplot(2, 1, 1)
            ax2.fill_between(dd.index, dd.values, 0, color='red', alpha=0.3)
            ax2.plot(dd.index, dd.values, color='red', linewidth=1)
            ax2.set_title("Drawdown %")
            ax2.set_ylabel("Drawdown")
            ax2.grid(True, alpha=0.3)
            
            # Monthly Heatmap
            ax3 = plt.subplot(2, 1, 2)
            monthly_rets = portfolio_log_returns.resample('M').apply(lambda x: np.exp(x.sum()) - 1)
            monthly_rets_df = pd.DataFrame(monthly_rets)
            monthly_rets_df['Year'] = monthly_rets_df.index.year
            monthly_rets_df['Month'] = monthly_rets_df.index.month
            pivot_rets = monthly_rets_df.pivot(index='Year', columns='Month', values=0)
            
            sns.heatmap(pivot_rets, annot=True, fmt=".1%", cmap="RdYlGn", center=0, ax=ax3, cbar=False)
            ax3.set_title("Monthly Returns")
            
            pdf.savefig(fig2)
            plt.close()
            
        return filename

    def generate_html_report(self, filename=None):
        """
        Generates a standalone HTML tearsheet for the backtest.
        """
        if filename is None:
            filename = f"backtests/{self.strat_name}_report.html"
            
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # --- DATA PREP ---
        # Aggregate Portfolio Return
        strat_rets_dict = {}
        for ticker in self.tickers:
            if ticker in self.data and 'strategy_return' in self.data[ticker].columns:
                strat_rets_dict[ticker] = self.data[ticker]['strategy_return']
                
        if not strat_rets_dict:
            return
            
        all_returns = pd.DataFrame(strat_rets_dict).fillna(0)
        # Equal weight portfolio
        portfolio_log_returns = np.log1p((np.exp(all_returns) - 1).mean(axis=1))
        portfolio_cum = np.exp(portfolio_log_returns.cumsum())
        
        # Benchmark
        bench_cum = None
        if self.benchmark_data is not None and not self.benchmark_data.empty:
            bench_cum = np.exp(self.benchmark_data['log_return'].cumsum())

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
            fig.add_trace(go.Scatter(x=bench_cum.index, y=bench_cum, name=f"Benchmark ({self.benchmark_ticker})",
                                     line=dict(color='gray', dash='dash')), row=1, col=1)

        # Drawdown
        peak = portfolio_cum.cummax()
        dd = (portfolio_cum - peak) / peak
        fig.add_trace(go.Scatter(x=dd.index, y=dd, name="Drawdown", 
                                 fill='tozeroy', line=dict(color='#EF553B')), row=2, col=1)

        fig.update_layout(template="plotly_white", height=600, title_text=f"Backtest Report: {self.strat_name}")
        
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
        
        # Calculate Metrics
        metrics = self.calculate_risk_metrics(portfolio_log_returns)

        # --- HTML GENERATION ---
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>IvyBT Report - {self.strat_name}</title>
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
                <p><strong>Strategy:</strong> {self.strat_name} | <strong>Range:</strong> {self.start_date} to {self.end_date}</p>
                
                <h2>Key Metrics (Portfolio)</h2>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-value">{portfolio_cum.iloc[-1]-1:.2%}</div>
                        <div class="metric-label">Total Return</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{metrics.get('Ann. Return', 'N/A')}</div>
                        <div class="metric-label">Ann. Return</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{metrics.get('Max Drawdown', 'N/A')}</div>
                        <div class="metric-label">Max Drawdown</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value">{metrics.get('Sharpe Ratio', 'N/A')}</div>
                        <div class="metric-label">Sharpe Ratio</div>
                    </div>
                     <div class="metric-card">
                        <div class="metric-value">{metrics.get('Sortino Ratio', 'N/A')}</div>
                        <div class="metric-label">Sortino Ratio</div>
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
