import { BarChart3, LineChart, Activity, TrendingUp, Zap, ShieldCheck, BarChart, Clock } from 'lucide-react';

const features = [
  {
    name: 'Random Strategy Generation',
    description:
      'Automatically create and test thousands of random strategy combinations with varying technical indicators.',
    icon: TrendingUp,
  },
  {
    name: 'Comprehensive Technical Indicators',
    description:
      'Access a library of over 100 technical indicators including moving averages, oscillators, volume profiles, and more.',
    icon: LineChart,
  },
  {
    name: 'Advanced Performance Metrics',
    description:
      'Evaluate strategies using Sharpe ratio, max drawdown, win rate, average trade ROI, and other key performance indicators.',
    icon: BarChart,
  },
  {
    name: 'Monte Carlo Analysis',
    description:
      'Use randomized simulations to identify robust strategies that perform well across different market conditions.',
    icon: Activity,
  },
  {
    name: 'Fast Simulation Engine',
    description:
      'Process thousands of candles and hundreds of strategies in seconds, allowing rapid iteration and discovery.',
    icon: Zap,
  },
  {
    name: 'Secure Cloud Storage',
    description:
      'Save your best simulations for later reference and comparison. Track your performance over time.',
    icon: ShieldCheck,
  },
];

export default function FeaturesSection() {
  return (
    <div className="bg-background/60 py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl lg:text-center">
          <h2 className="text-base font-semibold leading-7 text-chart-1">Trade Smarter</h2>
          <p className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">
            Everything you need to find your edge
          </p>
          <p className="mt-6 text-lg leading-8 text-muted-foreground">
            Quanticon combines powerful simulation technology with intuitive interfaces to help you discover profitable trading strategies.
          </p>
        </div>
        <div className="mx-auto mt-16 max-w-2xl sm:mt-20 lg:mt-24 lg:max-w-none">
          <dl className="grid max-w-xl grid-cols-1 gap-x-8 gap-y-16 lg:max-w-none lg:grid-cols-3">
            {features.map((feature) => (
              <div key={feature.name} className="flex flex-col">
                <dt className="flex items-center gap-x-3 text-base font-semibold leading-7">
                  <feature.icon className="h-5 w-5 flex-none text-chart-1" aria-hidden="true" />
                  {feature.name}
                </dt>
                <dd className="mt-4 flex flex-auto flex-col text-base leading-7 text-muted-foreground">
                  <p className="flex-auto">{feature.description}</p>
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </div>
  );
}