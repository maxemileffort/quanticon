import Link from 'next/link';
import { ArrowLeft, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';

interface SimulationSummaryProps {
  simulation: {
    id: string;
    symbol: string;
    timeframe: string;
    numFeatures: number;
    sharpeRatio: number;
    winRate: number;
    [key: string]: any;
  };
}

export default function SimulationSummary({ simulation }: SimulationSummaryProps) {
  const formatDate = (date: Date) => {
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: 'numeric',
    }).format(date);
  };

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8">
        <div>
          <div className="flex items-center mb-2">
            <Link href="/dashboard">
              <Button variant="ghost" size="icon" className="mr-2">
                <ArrowLeft className="h-4 w-4" />
              </Button>
            </Link>
            <h1 className="text-3xl font-bold tracking-tight">Simulation Results</h1>
          </div>
          <div className="flex items-center flex-wrap gap-2">
            <Badge className="text-sm">{simulation.symbol}</Badge>
            <Badge variant="outline" className="text-sm">{simulation.timeframe}</Badge>
            <Badge variant="outline" className="text-sm">{simulation.numFeatures} indicators</Badge>
            <Badge variant="outline" className="text-sm">{formatDate(simulation.runDate)}</Badge>
          </div>
        </div>
        <div className="mt-4 sm:mt-0 flex items-center gap-2">
          <Button variant="outline" size="sm" className="gap-1">
            <Download className="h-3.5 w-3.5" />
            Export
          </Button>
          <Button size="sm">Save Strategy</Button>
        </div>
      </div>
      
      <Card className="bg-card mb-8">
        <CardContent className="pt-6">
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-1">Sharpe Ratio</h3>
              <p className={`text-2xl font-bold font-mono ${simulation.sharpeRatio >= 1.5 ? 'text-chart-1' : ''}`}>
                {simulation.sharpeRatio.toFixed(2)}
              </p>
            </div>
            
            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-1">Win Rate</h3>
              <p className="text-2xl font-bold font-mono">
                {(simulation.winRate * 100).toFixed(1)}%
              </p>
            </div>
            
            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-1">Max Drawdown</h3>
              <p className="text-2xl font-bold font-mono text-destructive">
                {simulation.maxDrawdown.toFixed(1)}%
              </p>
            </div>
            
            <div>
              <h3 className="text-sm font-medium text-muted-foreground mb-1">Total Return</h3>
              <p className={`text-2xl font-bold font-mono ${simulation.totalReturns > 0 ? 'text-chart-1' : 'text-destructive'}`}>
                {simulation.totalReturns.toFixed(1)}%
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}