'use client';

import { useState } from 'react';
import Link from 'next/link';
import { formatDistanceToNow } from 'date-fns';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ArrowUpDown, Eye } from 'lucide-react';

// Mock data for demonstrations
const mockSimulations = [
  {
    id: '1',
    symbol: 'SPY',
    timeframe: 'Daily',
    numFeatures: 5,
    sharpeRatio: 1.85,
    winRate: 0.685,
    runDate: new Date('2025-04-01'),
  },
  {
    id: '2',
    symbol: 'QQQ',
    timeframe: '4h',
    numFeatures: 3,
    sharpeRatio: 1.62,
    winRate: 0.712,
    runDate: new Date('2025-03-29'),
  },
  {
    id: '3',
    symbol: 'AAPL',
    timeframe: 'Daily',
    numFeatures: 7,
    sharpeRatio: 1.34,
    winRate: 0.623,
    runDate: new Date('2025-03-27'),
  },
  {
    id: '4',
    symbol: 'BTC-USD',
    timeframe: '1h',
    numFeatures: 6,
    sharpeRatio: 2.05,
    winRate: 0.589,
    runDate: new Date('2025-03-25'),
  },
  {
    id: '5',
    symbol: 'AMZN',
    timeframe: 'Daily',
    numFeatures: 4,
    sharpeRatio: 1.27,
    winRate: 0.655,
    runDate: new Date('2025-03-22'),
  },
];

export default function RecentSimulations() {
  const [sortBy, setSortBy] = useState<string>('runDate');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const sortedSimulations = [...mockSimulations].sort((a, b) => {
    if (sortBy === 'runDate') {
      return sortOrder === 'asc' 
        ? a.runDate.getTime() - b.runDate.getTime()
        : b.runDate.getTime() - a.runDate.getTime();
    } else if (sortBy === 'sharpeRatio') {
      return sortOrder === 'asc' ? a.sharpeRatio - b.sharpeRatio : b.sharpeRatio - a.sharpeRatio;
    } else if (sortBy === 'winRate') {
      return sortOrder === 'asc' ? a.winRate - b.winRate : b.winRate - a.winRate;
    }
    return 0;
  });

  const handleSort = (column: string) => {
    if (sortBy === column) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(column);
      setSortOrder('desc');
    }
  };

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Symbol</TableHead>
            <TableHead>Timeframe</TableHead>
            <TableHead>Indicators</TableHead>
            <TableHead>
              <div 
                className="flex items-center cursor-pointer"
                onClick={() => handleSort('sharpeRatio')}
              >
                Sharpe Ratio
                <ArrowUpDown className="ml-1 h-3.5 w-3.5" />
              </div>
            </TableHead>
            <TableHead>
              <div 
                className="flex items-center cursor-pointer"
                onClick={() => handleSort('winRate')}
              >
                Win Rate
                <ArrowUpDown className="ml-1 h-3.5 w-3.5" />
              </div>
            </TableHead>
            <TableHead>
              <div 
                className="flex items-center cursor-pointer"
                onClick={() => handleSort('runDate')}
              >
                Run Date
                <ArrowUpDown className="ml-1 h-3.5 w-3.5" />
              </div>
            </TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedSimulations.map((sim) => (
            <TableRow key={sim.id}>
              <TableCell className="font-medium">{sim.symbol}</TableCell>
              <TableCell>{sim.timeframe}</TableCell>
              <TableCell>{sim.numFeatures}</TableCell>
              <TableCell className="font-mono">
                {sim.sharpeRatio.toFixed(2)}
              </TableCell>
              <TableCell className="font-mono">
                {(sim.winRate * 100).toFixed(1)}%
              </TableCell>
              <TableCell>
                {formatDistanceToNow(sim.runDate, { addSuffix: true })}
              </TableCell>
              <TableCell className="text-right">
                <Link href={`/results/${sim.id}`}>
                  <Button variant="ghost" size="icon">
                    <Eye className="h-4 w-4" />
                  </Button>
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}