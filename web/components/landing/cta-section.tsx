import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { TrendingUp } from 'lucide-react';

export default function CTASection() {
  return (
    <div className="bg-card">
      <div className="px-6 py-24 sm:px-6 sm:py-32 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Ready to discover your edge?
            <br />
            Start simulating today.
          </h2>
          <p className="mx-auto mt-6 max-w-xl text-lg leading-8 text-muted-foreground">
            Join traders who are using Monte Carlo simulations to find profitable strategies in any market condition.
          </p>
          <div className="mt-10 flex items-center justify-center gap-x-6">
            <Link href="/signup">
              <Button size="lg" className="gap-2">
                Get started
                <TrendingUp className="h-4 w-4" />
              </Button>
            </Link>
            <Link
              href="/pricing"
              className="text-sm font-semibold leading-6 text-foreground hover:text-muted-foreground"
            >
              View pricing <span aria-hidden="true">→</span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}