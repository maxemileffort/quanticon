interface StatsTableProps {
  simulation: {
    sharpeRatio: number;
    maxDrawdown: number;
    winRate: number;
    profitFactor: number;
    totalReturns: number;
    averageTrade: number;
    [key: string]: any;
  };
}

export default function StatsTable({ simulation }: StatsTableProps) {
  return (
    <div className="grid gap-2">
      <div className="flex justify-between py-2 border-b">
        <div className="text-sm font-medium text-muted-foreground">Sharpe Ratio</div>
        <div className="font-mono font-medium">{simulation.sharpeRatio.toFixed(2)}</div>
      </div>
      <div className="flex justify-between py-2 border-b">
        <div className="text-sm font-medium text-muted-foreground">Max Drawdown</div>
        <div className="font-mono font-medium">{simulation.maxDrawdown.toFixed(1)}%</div>
      </div>
      <div className="flex justify-between py-2 border-b">
        <div className="text-sm font-medium text-muted-foreground">Win Rate</div>
        <div className="font-mono font-medium">{(simulation.winRate * 100).toFixed(1)}%</div>
      </div>
      <div className="flex justify-between py-2 border-b">
        <div className="text-sm font-medium text-muted-foreground">Profit Factor</div>
        <div className="font-mono font-medium">{simulation.profitFactor.toFixed(2)}</div>
      </div>
      <div className="flex justify-between py-2 border-b">
        <div className="text-sm font-medium text-muted-foreground">Total Return</div>
        <div className="font-mono font-medium">{simulation.totalReturns.toFixed(1)}%</div>
      </div>
      <div className="flex justify-between py-2">
        <div className="text-sm font-medium text-muted-foreground">Average Trade</div>
        <div className="font-mono font-medium">{simulation.averageTrade.toFixed(2)}%</div>
      </div>
    </div>
  );
}