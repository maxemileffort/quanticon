'use client';

import { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

// Generate mock equity curve data
const generateMockEquityCurve = (id: string) => {
  const data = [];
  let equity = 10000;
  let benchmark = 10000;
  
  // Different pattern based on ID
  const multiplier = id === '1' ? 1.1 : id === '2' ? 0.9 : 1.05;
  const volatility = id === '1' ? 0.03 : id === '2' ? 0.05 : 0.04;
  
  for (let i = 0; i < 252; i++) {
    // Strategy performance with some randomness
    const strategyChange = (Math.random() * 0.02 - 0.005) * multiplier;
    equity = equity * (1 + strategyChange);
    
    // Benchmark performance with different randomness
    const benchmarkChange = (Math.random() * 0.01 - 0.002);
    benchmark = benchmark * (1 + benchmarkChange);
    
    // Add some drawdowns
    if (i > 60 && i < 80) {
      equity = equity * 0.995;
    }
    
    if (i > 150 && i < 170) {
      benchmark = benchmark * 0.997;
    }
    
    data.push({
      date: new Date(2024, 0, i + 1).toISOString().split('T')[0],
      strategy: Math.round(equity * 100) / 100,
      benchmark: Math.round(benchmark * 100) / 100,
    });
  }
  
  return data;
};

interface EquityCurveChartProps {
  simulationId: string;
}

export default function EquityCurveChart({ simulationId }: EquityCurveChartProps) {
  const [chartData, setChartData] = useState<any[]>([]);
  const [comparisonType, setComparisonType] = useState('benchmark');
  
  useEffect(() => {
    // In a real app, this would fetch from an API
    const data = generateMockEquityCurve(simulationId);
    setChartData(data);
  }, [simulationId]);
  
  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Select 
          value={comparisonType} 
          onValueChange={setComparisonType}
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Compare with" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="benchmark">Benchmark (SPY)</SelectItem>
            <SelectItem value="buyhold">Buy & Hold</SelectItem>
            <SelectItem value="none">No Comparison</SelectItem>
          </SelectContent>
        </Select>
      </div>
      
      <div className="h-[400px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{
              top: 5,
              right: 30,
              left: 20,
              bottom: 5,
            }}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis 
              dataKey="date" 
              tick={{ fontSize: 12 }}
              tickFormatter={(tick) => {
                const date = new Date(tick);
                return `${date.getMonth() + 1}/${date.getDate()}`;
              }}
              minTickGap={30}
            />
            <YAxis 
              tick={{ fontSize: 12 }}
              tickFormatter={(tick) => `$${tick.toLocaleString()}`}
            />
            <Tooltip 
              formatter={(value: number) => [`$${value.toLocaleString()}`, '']}
              labelFormatter={(label) => {
                const date = new Date(label);
                return date.toLocaleDateString();
              }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="strategy"
              name="Strategy"
              stroke="hsl(var(--chart-1))"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 6 }}
            />
            {comparisonType !== 'none' && (
              <Line
                type="monotone"
                dataKey="benchmark"
                name={comparisonType === 'benchmark' ? 'Benchmark (SPY)' : 'Buy & Hold'}
                stroke="hsl(var(--chart-2))"
                strokeWidth={2}
                dot={false}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}