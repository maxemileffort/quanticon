import { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import SimulationSummary from '@/components/results/simulation-summary';
import EquityCurveChart from '@/components/results/equity-curve-chart';
import IndicatorsTable from '@/components/results/indicators-table';
import StatsTable from '@/components/results/stats-table';
import TradeBreakdown from '@/components/results/trade-breakdown';

export const metadata: Metadata = {
  title: 'Simulation Results | Quanticon',
  description: 'Detailed analysis of your Monte Carlo trading simulation results.',
};

// For demonstration purposes - in a real app, this would come from an API/database
const getMockSimulation = (id: string) => {
  // Hardcoded new result for the redirect from form submission
  if (id === 'new') {
    return {
      id: 'new',
      symbol: 'AAPL',
      timeframe: 'Daily',
      numFeatures: 4,
      targetRoi: 2.0,
      lookbackPeriod: 252,
      useVolatilityScaling: true,
      includeSentiment: false,
      runDate: new Date(),
      sharpeRatio: 1.73,
      maxDrawdown: -14.2,
      winRate: 0.64,
      profitFactor: 1.89,
      totalReturns: 37.8,
      averageTrade: 1.12,
    };
  }
  
  const simulations = [
    {
      id: '1',
      symbol: 'SPY',
      timeframe: 'Daily',
      numFeatures: 5,
      targetRoi: 2.0,
      lookbackPeriod: 252,
      useVolatilityScaling: true,
      includeSentiment: true,
      runDate: new Date('2025-04-01'),
      sharpeRatio: 1.85,
      maxDrawdown: -12.4,
      winRate: 0.685,
      profitFactor: 2.15,
      totalReturns: 42.6,
      averageTrade: 1.23,
    },
    {
      id: '2',
      symbol: 'QQQ',
      timeframe: '4h',
      numFeatures: 3,
      targetRoi: 1.5,
      lookbackPeriod: 500,
      useVolatilityScaling: false,
      includeSentiment: false,
      runDate: new Date('2025-03-29'),
      sharpeRatio: 1.62,
      maxDrawdown: -18.7,
      winRate: 0.712,
      profitFactor: 1.94,
      totalReturns: 32.8,
      averageTrade: 0.98,
    },
  ];
  
  return simulations.find(sim => sim.id === id);
};

export default function ResultsPage({ params }: { params: { id: string } }) {
  const simulation = getMockSimulation(params.id);
  
  if (!simulation) {
    notFound();
  }
  
  return (
    <div className="container max-w-7xl mx-auto px-4 py-8">
      <SimulationSummary simulation={simulation} />
      
      <Tabs defaultValue="overview" className="mt-8">
        <TabsList className="mb-4 grid w-full max-w-md grid-cols-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="indicators">Indicators</TabsTrigger>
          <TabsTrigger value="statistics">Statistics</TabsTrigger>
          <TabsTrigger value="trades">Trades</TabsTrigger>
        </TabsList>
        
        <TabsContent value="overview" className="space-y-8">
          <Card>
            <CardHeader>
              <CardTitle>Equity Curve</CardTitle>
            </CardHeader>
            <CardContent>
              <EquityCurveChart simulationId={simulation.id} />
            </CardContent>
          </Card>
          
          <div className="grid gap-8 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Performance Metrics</CardTitle>
              </CardHeader>
              <CardContent>
                <StatsTable simulation={simulation} />
              </CardContent>
            </Card>
            
            <Card>
              <CardHeader>
                <CardTitle>Strategy Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground">Strategy Type</h4>
                    <p>Momentum + Mean Reversion</p>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground">Best Market Condition</h4>
                    <p>Trending markets with moderate volatility</p>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground">Worst Market Condition</h4>
                    <p>Sideways markets with low volatility</p>
                  </div>
                  <div>
                    <h4 className="text-sm font-medium text-muted-foreground">Recommendations</h4>
                    <p>Consider adding volatility filters to improve performance in ranging markets</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
        
        <TabsContent value="indicators">
          <Card>
            <CardHeader>
              <CardTitle>Technical Indicators</CardTitle>
            </CardHeader>
            <CardContent>
              <IndicatorsTable simulationId={simulation.id} />
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="statistics">
          <Card>
            <CardHeader>
              <CardTitle>Detailed Statistics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="bg-card rounded-lg border p-4">
                    <div className="text-sm font-medium text-muted-foreground">Sharpe Ratio</div>
                    <div className="font-mono text-2xl font-bold">{simulation.sharpeRatio.toFixed(2)}</div>
                  </div>
                  <div className="bg-card rounded-lg border p-4">
                    <div className="text-sm font-medium text-muted-foreground">Max Drawdown</div>
                    <div className="font-mono text-2xl font-bold">{simulation.maxDrawdown.toFixed(1)}%</div>
                  </div>
                  <div className="bg-card rounded-lg border p-4">
                    <div className="text-sm font-medium text-muted-foreground">Win Rate</div>
                    <div className="font-mono text-2xl font-bold">{(simulation.winRate * 100).toFixed(1)}%</div>
                  </div>
                  <div className="bg-card rounded-lg border p-4">
                    <div className="text-sm font-medium text-muted-foreground">Profit Factor</div>
                    <div className="font-mono text-2xl font-bold">{simulation.profitFactor.toFixed(2)}</div>
                  </div>
                </div>
                
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-4">
                    <h3 className="text-lg font-medium">Returns</h3>
                    <div className="bg-card rounded-lg border divide-y">
                      <div className="flex justify-between px-4 py-3">
                        <div className="text-sm font-medium text-muted-foreground">Total Returns</div>
                        <div className="font-mono font-medium">{simulation.totalReturns.toFixed(1)}%</div>
                      </div>
                      <div className="flex justify-between px-4 py-3">
                        <div className="text-sm font-medium text-muted-foreground">Annualized Returns</div>
                        <div className="font-mono font-medium">{(simulation.totalReturns / (simulation.lookbackPeriod / 252) * 100 / 100).toFixed(1)}%</div>
                      </div>
                      <div className="flex justify-between px-4 py-3">
                        <div className="text-sm font-medium text-muted-foreground">Average Trade</div>
                        <div className="font-mono font-medium">{simulation.averageTrade.toFixed(2)}%</div>
                      </div>
                      <div className="flex justify-between px-4 py-3">
                        <div className="text-sm font-medium text-muted-foreground">Average Win</div>
                        <div className="font-mono font-medium">{(simulation.averageTrade * 1.5).toFixed(2)}%</div>
                      </div>
                      <div className="flex justify-between px-4 py-3">
                        <div className="text-sm font-medium text-muted-foreground">Average Loss</div>
                        <div className="font-mono font-medium">{(simulation.averageTrade * -0.8).toFixed(2)}%</div>
                      </div>
                    </div>
                  </div>
                  
                  <div className="space-y-4">
                    <h3 className="text-lg font-medium">Risk Metrics</h3>
                    <div className="bg-card rounded-lg border divide-y">
                      <div className="flex justify-between px-4 py-3">
                        <div className="text-sm font-medium text-muted-foreground">Sortino Ratio</div>
                        <div className="font-mono font-medium">{(simulation.sharpeRatio * 1.2).toFixed(2)}</div>
                      </div>
                      <div className="flex justify-between px-4 py-3">
                        <div className="text-sm font-medium text-muted-foreground">Calmar Ratio</div>
                        <div className="font-mono font-medium">{(simulation.totalReturns / Math.abs(simulation.maxDrawdown)).toFixed(2)}</div>
                      </div>
                      <div className="flex justify-between px-4 py-3">
                        <div className="text-sm font-medium text-muted-foreground">Recovery Factor</div>
                        <div className="font-mono font-medium">{(simulation.totalReturns / Math.abs(simulation.maxDrawdown)).toFixed(2)}</div>
                      </div>
                      <div className="flex justify-between px-4 py-3">
                        <div className="text-sm font-medium text-muted-foreground">Expected Payoff</div>
                        <div className="font-mono font-medium">{simulation.averageTrade.toFixed(2)}%</div>
                      </div>
                      <div className="flex justify-between px-4 py-3">
                        <div className="text-sm font-medium text-muted-foreground">Std. Deviation</div>
                        <div className="font-mono font-medium">{(simulation.averageTrade * 3).toFixed(2)}%</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="trades">
          <Card>
            <CardHeader>
              <CardTitle>Trade Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <TradeBreakdown simulationId={simulation.id} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}