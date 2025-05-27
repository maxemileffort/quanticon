import { Metadata } from 'next';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import DashboardHeader from '@/components/dashboard/dashboard-header';
import RecentSimulations from '@/components/dashboard/recent-simulations';
import QuickStats from '@/components/dashboard/quick-stats';
import { ArrowRight } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Dashboard | Quanticon',
  description: 'View your simulation history and create new trading strategies.',
};

export default function DashboardPage() {
  return (
    <div className="container max-w-7xl mx-auto px-4 py-6">
      <DashboardHeader />
      
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 mb-8">
        <QuickStats />
      </div>
      
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">Recent Simulations</h2>
          <Link href="/dashboard/simulations">
            <Button variant="outline" size="sm" className="gap-1">
              View all
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        </div>
        <RecentSimulations />
      </div>
      
      <div className="bg-card rounded-lg border border-border p-6 shadow-sm">
        <h2 className="text-xl font-semibold mb-4">Start a New Simulation</h2>
        <p className="text-muted-foreground mb-6">
          Configure and run a new Monte Carlo simulation to discover profitable trading strategies.
        </p>
        <Link href="/simulate">
          <Button className="gap-2">
            New Simulation
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </div>
    </div>
  );
}