import { CircleDigit1, CircleDigit2, CircleDigit3, CircleDigit4 } from '@/components/ui/circle-digits';

export default function HowItWorksSection() {
  return (
    <div className="bg-card py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl lg:text-center">
          <h2 className="text-base font-semibold leading-7 text-chart-1">Simple Process</h2>
          <p className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">
            How Quanticon Works
          </p>
          <p className="mt-6 text-lg leading-8 text-muted-foreground">
            Our platform simplifies the complex process of strategy discovery through four easy steps.
          </p>
        </div>
        <div className="mx-auto mt-16 max-w-2xl sm:mt-20 lg:mt-24 lg:max-w-none">
          <div className="grid gap-8 lg:grid-cols-4 lg:gap-x-12">
            <div className="relative">
              <div className="flex flex-col items-center text-center">
                <div className="mb-4">
                  <CircleDigit1 />
                </div>
                <h3 className="text-xl font-bold">Select Your Asset</h3>
                <p className="mt-3 text-muted-foreground">Choose the financial instrument and timeframe you want to analyze.</p>
              </div>
              <div className="hidden lg:block absolute top-12 left-full w-12 h-0.5 bg-border"></div>
            </div>
            
            <div className="relative">
              <div className="flex flex-col items-center text-center">
                <div className="mb-4">
                  <CircleDigit2 />
                </div>
                <h3 className="text-xl font-bold">Configure Parameters</h3>
                <p className="mt-3 text-muted-foreground">Specify the number of indicators and target ROI for your strategy.</p>
              </div>
              <div className="hidden lg:block absolute top-12 left-full w-12 h-0.5 bg-border"></div>
            </div>
            
            <div className="relative">
              <div className="flex flex-col items-center text-center">
                <div className="mb-4">
                  <CircleDigit3 />
                </div>
                <h3 className="text-xl font-bold">Run Simulation</h3>
                <p className="mt-3 text-muted-foreground">Our system generates and evaluates thousands of random strategies.</p>
              </div>
              <div className="hidden lg:block absolute top-12 left-full w-12 h-0.5 bg-border"></div>
            </div>
            
            <div>
              <div className="flex flex-col items-center text-center">
                <div className="mb-4">
                  <CircleDigit4 />
                </div>
                <h3 className="text-xl font-bold">Analyze Results</h3>
                <p className="mt-3 text-muted-foreground">Review performance metrics and save the best strategies for further testing.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}