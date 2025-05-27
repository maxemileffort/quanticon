'use client';

import { useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';

// Generate mock trades
const generateMockTrades = (id: string) => {
  const trades = [];
  const numTrades = 50;
  
  // Adjust win rate based on simulation ID
  let winRate = id === '1' ? 0.685 : id === '2' ? 0.712 : 0.64;
  
  // Generate entry/exit dates
  let currentDate = new Date(2024, 0, 1);
  
  for (let i = 0; i < numTrades; i++) {
    // Random holding period between 1-10 days
    const holdingPeriod = Math.floor(Math.random() * 10) + 1;
    
    // Entry date
    const entryDate = new Date(currentDate);
    
    // Move current date forward
    currentDate.setDate(currentDate.getDate() + holdingPeriod + Math.floor(Math.random() * 3));
    
    // Exit date
    const exitDate = new Date(currentDate);
    
    // Determine if win or loss
    const isWin = Math.random() < winRate;
    
    // Calculate profit/loss - wins tend to be larger than losses (asymmetric return)
    let profitLoss;
    if (isWin) {
      profitLoss = (Math.random() * 2 + 1); // 1-3%
    } else {
      profitLoss = -(Math.random() * 1.5 + 0.5); // -0.5 to -2%
    }
    
    trades.push({
      id: i + 1,
      entryDate: entryDate.toISOString().split('T')[0],
      exitDate: exitDate.toISOString().split('T')[0],
      holdingPeriod,
      profitLoss: profitLoss,
      result: isWin ? 'Win' : 'Loss',
    });
  }
  
  // Sort by entry date
  return trades.sort((a, b) => new Date(a.entryDate).getTime() - new Date(b.entryDate).getTime());
};

// Prepare distribution data
const prepareDistributionData = (trades: any[]) => {
  // Group trades by profit/loss range
  const ranges = [
    { min: -3, max: -2, label: '-3% to -2%' },
    { min: -2, max: -1, label: '-2% to -1%' },
    { min: -1, max: -0.5, label: '-1% to -0.5%' },
    { min: -0.5, max: 0, label: '-0.5% to 0%' },
    { min: 0, max: 0.5, label: '0% to 0.5%' },
    { min: 0.5, max: 1, label: '0.5% to 1%' },
    { min: 1, max: 2, label: '1% to 2%' },
    { min: 2, max: 3, label: '2% to 3%' },
    { min: 3, max: 4, label: '3% to 4%' },
  ];
  
  const distribution = ranges.map(range => {
    const count = trades.filter(trade => 
      trade.profitLoss >= range.min && trade.profitLoss < range.max
    ).length;
    
    return {
      range: range.label,
      count,
      color: range.min >= 0 ? 'gain' : 'loss',
    };
  });
  
  return distribution;
};

interface TradeBreakdownProps {
  simulationId: string;
}

export default function TradeBreakdown({ simulationId }: TradeBreakdownProps) {
  const [selectedTab, setSelectedTab] = useState('list');
  const trades = generateMockTrades(simulationId);
  const distributionData = prepareDistributionData(trades);
  
  return (
    <Tabs value={selectedTab} onValueChange={setSelectedTab}>
      <TabsList className="mb-4 grid w-full max-w-md grid-cols-2">
        <TabsTrigger value="list">Trade List</TabsTrigger>
        <TabsTrigger value="distribution">Distribution</TabsTrigger>
      </TabsList>
      
      <TabsContent value="list">
        <div className="rounded-md border overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Entry Date</TableHead>
                <TableHead>Exit Date</TableHead>
                <TableHead className="text-center">Days</TableHead>
                <TableHead className="text-right">Profit/Loss</TableHead>
                <TableHead className="text-right">Result</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {trades.slice(0, 15).map((trade) => (
                <TableRow key={trade.id}>
                  <TableCell>{trade.id}</TableCell>
                  <TableCell>{trade.entryDate}</TableCell>
                  <TableCell>{trade.exitDate}</TableCell>
                  <TableCell className="text-center">{trade.holdingPeriod}</TableCell>
                  <TableCell 
                    className={`text-right font-mono ${trade.profitLoss >= 0 ? 'text-chart-1' : 'text-destructive'}`}
                  >
                    {trade.profitLoss.toFixed(2)}%
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge variant={trade.result === 'Win' ? 'default' : 'destructive'}>
                      {trade.result}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
        <div className="mt-4 text-sm text-muted-foreground text-center">
          Showing 15 of {trades.length} trades
        </div>
      </TabsContent>
      
      <TabsContent value="distribution">
        <div className="h-[400px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={distributionData}
              margin={{
                top: 20,
                right: 30,
                left: 20,
                bottom: 60,
              }}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="range" 
                angle={-45} 
                textAnchor="end" 
                tick={{ fontSize: 12 }}
                height={60}
              />
              <YAxis />
              <Tooltip 
                formatter={(value: number) => [`${value} trades`, 'Count']}
              />
              <Bar 
                dataKey="count" 
                name="Number of Trades"
                fill={(data) => data.color === 'gain' ? 'hsl(var(--chart-1))' : 'hsl(var(--destructive))'}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </TabsContent>
    </Tabs>
  );
}