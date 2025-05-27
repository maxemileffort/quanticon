import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { BarChart3, TrendingUp, ArrowRight } from 'lucide-react';

export default function HeroSection() {
  return (
    <div className="relative isolate overflow-hidden">
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(45%_40%_at_50%_60%,hsl(var(--chart-1)/15%),transparent),radial-gradient(30%_30%_at_35%_25%,hsl(var(--chart-2)/20%),transparent)]"></div>

      <div className="mx-auto max-w-7xl px-6 py-24 sm:py-32 lg:px-8 lg:py-40">
        <div className="mx-auto max-w-2xl lg:mx-0 lg:max-w-xl">
          <div className="flex items-center gap-x-4 text-xs">
            <span className="rounded-full bg-primary/10 px-3 py-1 font-medium text-primary ring-1 ring-inset ring-primary/20">
              Beta Access
            </span>
            <span className="inline-flex items-center gap-x-1.5 rounded-full px-2 py-1 font-medium text-muted-foreground">
              <BarChart3 className="h-4 w-4 fill-primary/20 text-primary" aria-hidden="true" />
              Limited-time offer
            </span>
          </div>
          <h1 className="mt-10 text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl">
            <span>Monte Carlo</span>{' '}
            <span className="text-chart-1">your way</span>{' '}
            <span>to smarter trades</span>
          </h1>
          <p className="mt-6 text-lg leading-8 text-muted-foreground">
            Discover profitable trading strategies through randomized simulations. Quanticon empowers you to explore the vast
            universe of technical indicators and find what really works for your trading style.
          </p>
          <div className="mt-10 flex items-center gap-x-6">
            <Link href="/simulate">
              <Button size="lg" className="gap-2">
                Try it now <ArrowRight className="h-4 w-4 opacity-70" />
              </Button>
            </Link>
            <Link href="/dashboard" className="text-sm font-semibold leading-6 text-foreground hover:text-muted-foreground">
              View dashboard <span aria-hidden="true">→</span>
            </Link>
          </div>
        </div>
        <div className="mt-16 sm:mt-24 lg:mt-0 lg:flex-1 lg:ml-auto">
          <div className="relative aspect-[4/3] overflow-hidden rounded-xl border border-border bg-card/50 shadow-lg backdrop-blur-sm transition-all hover:bg-card/80">
            <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
              <div className="p-6 w-full h-full flex flex-col">
                <div className="text-left mb-4">
                  <h3 className="text-sm font-medium text-muted-foreground">Monte Carlo Simulation</h3>
                  <p className="text-xs text-muted-foreground/70">Results for SPY / Daily / 5 Indicators</p>
                </div>
                <div className="flex-1 flex items-center justify-center">
                  <TrendingUp className="h-32 w-32 text-chart-1" />
                </div>
                <div className="grid grid-cols-2 gap-3 mt-2">
                  <div className="text-xs">
                    <p className="text-muted-foreground/70">Sharpe Ratio</p>
                    <p className="font-mono text-sm">1.85</p>
                  </div>
                  <div className="text-xs">
                    <p className="text-muted-foreground/70">Win Rate</p>
                    <p className="font-mono text-sm">68.5%</p>
                  </div>
                  <div className="text-xs">
                    <p className="text-muted-foreground/70">Max Drawdown</p>
                    <p className="font-mono text-sm">-12.4%</p>
                  </div>
                  <div className="text-xs">
                    <p className="text-muted-foreground/70">Avg. ROI/Trade</p>
                    <p className="font-mono text-sm">1.23%</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}