'use client';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';

// Mock data generator
const generateIndicators = (id: string) => {
  // Indicators library with parameters
  const indicatorsList = [
    { name: 'Simple Moving Average (SMA)', type: 'Trend', params: { period: 20 }, weight: 1.2 },
    { name: 'Exponential Moving Average (EMA)', type: 'Trend', params: { period: 10 }, weight: 1.5 },
    { name: 'Relative Strength Index (RSI)', type: 'Oscillator', params: { period: 14, overbought: 70, oversold: 30 }, weight: 2.1 },
    { name: 'Moving Average Convergence Divergence (MACD)', type: 'Trend', params: { fast: 12, slow: 26, signal: 9 }, weight: 1.8 },
    { name: 'Bollinger Bands', type: 'Volatility', params: { period: 20, stdDev: 2 }, weight: 1.7 },
    { name: 'Average True Range (ATR)', type: 'Volatility', params: { period: 14 }, weight: 0.8 },
    { name: 'Stochastic Oscillator', type: 'Oscillator', params: { periodK: 14, periodD: 3 }, weight: 1.6 },
    { name: 'Average Directional Index (ADX)', type: 'Trend', params: { period: 14 }, weight: 1.3 },
    { name: 'Ichimoku Cloud', type: 'Trend', params: { conversionPeriod: 9, basePeriod: 26, laggingSpan2Period: 52, displacement: 26 }, weight: 1.4 },
    { name: 'On-Balance Volume (OBV)', type: 'Volume', params: {}, weight: 0.9 },
  ];
  
  // Different selections based on simulation ID
  if (id === '1') {
    return [
      indicatorsList[2], // RSI
      indicatorsList[3], // MACD
      indicatorsList[0], // SMA
      indicatorsList[4], // Bollinger Bands
      indicatorsList[6], // Stochastic
    ];
  } else if (id === '2') {
    return [
      indicatorsList[1], // EMA
      indicatorsList[7], // ADX
      indicatorsList[9], // OBV
    ];
  } else if (id === 'new') {
    return [
      indicatorsList[0], // SMA
      indicatorsList[4], // Bollinger Bands
      indicatorsList[5], // ATR
      indicatorsList[9], // OBV
    ];
  } else {
    // Return random selection
    return Array(5).fill(0).map(() => {
      const randIndex = Math.floor(Math.random() * indicatorsList.length);
      return indicatorsList[randIndex];
    });
  }
};

// Format parameters to be human-readable
const formatParams = (params: Record<string, any>) => {
  return Object.entries(params).map(([key, value]) => {
    return `${key.charAt(0).toUpperCase() + key.slice(1)}: ${value}`;
  }).join(', ');
};

interface IndicatorsTableProps {
  simulationId: string;
}

export default function IndicatorsTable({ simulationId }: IndicatorsTableProps) {
  const indicators = generateIndicators(simulationId);
  
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Indicator</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Parameters</TableHead>
          <TableHead className="text-right">Weight</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {indicators.map((indicator, index) => (
          <TableRow key={index}>
            <TableCell className="font-medium">{indicator.name}</TableCell>
            <TableCell>
              <Badge variant="outline">{indicator.type}</Badge>
            </TableCell>
            <TableCell className="font-mono text-xs">
              {formatParams(indicator.params)}
            </TableCell>
            <TableCell className="text-right font-mono">
              {indicator.weight.toFixed(1)}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}