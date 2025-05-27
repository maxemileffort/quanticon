'use client';

import { useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import { Checkbox } from '@/components/ui/checkbox';
import { Card, CardContent } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';

const formSchema = z.object({
  symbol: z.string().min(1, {
    message: 'Please select a symbol.',
  }),
  timeframe: z.string().min(1, {
    message: 'Please select a timeframe.',
  }),
  lookbackPeriod: z.coerce.number().int().min(30).max(1000),
  numIndicators: z.coerce.number().int().min(1).max(10),
  targetRoi: z.coerce.number().min(0.1).max(10),
  useVolatilityScaling: z.boolean().default(false),
  includeSentiment: z.boolean().default(false),
});

const symbols = [
  { label: 'SPY (S&P 500 ETF)', value: 'SPY' },
  { label: 'QQQ (Nasdaq ETF)', value: 'QQQ' },
  { label: 'AAPL (Apple)', value: 'AAPL' },
  { label: 'MSFT (Microsoft)', value: 'MSFT' },
  { label: 'TSLA (Tesla)', value: 'TSLA' },
  { label: 'AMZN (Amazon)', value: 'AMZN' },
  { label: 'BTC-USD (Bitcoin)', value: 'BTC-USD' },
  { label: 'ETH-USD (Ethereum)', value: 'ETH-USD' },
];

const timeframes = [
  { label: '1 Hour', value: '1h' },
  { label: '4 Hours', value: '4h' },
  { label: 'Daily', value: '1d' },
  { label: 'Weekly', value: '1w' },
];

export default function SimulationForm() {
  const [isSimulating, setIsSimulating] = useState(false);
  const router = useRouter();
  
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      symbol: '',
      timeframe: '',
      lookbackPeriod: 252,
      numIndicators: 5,
      targetRoi: 2,
      useVolatilityScaling: true,
      includeSentiment: false,
    },
  });

  function onSubmit(values: z.infer<typeof formSchema>) {
    setIsSimulating(true);
    
    // Simulate API call/processing delay
    setTimeout(() => {
      setIsSimulating(false);
      
      // Redirect to a mock result page
      router.push('/results/new');
    }, 3000);
  }

  return (
    <Card>
      <CardContent className="pt-6">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <FormField
                control={form.control}
                name="symbol"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Symbol</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select an asset" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {symbols.map((symbol) => (
                          <SelectItem key={symbol.value} value={symbol.value}>
                            {symbol.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      The financial instrument to analyze.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="timeframe"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Timeframe</FormLabel>
                    <Select onValueChange={field.onChange} defaultValue={field.value}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Select a timeframe" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {timeframes.map((timeframe) => (
                          <SelectItem key={timeframe.value} value={timeframe.value}>
                            {timeframe.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      The timeframe for your analysis.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="lookbackPeriod"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Lookback Period</FormLabel>
                  <FormControl>
                    <div className="flex items-center space-x-4">
                      <Input
                        type="number"
                        {...field}
                        className="w-24"
                        min={30}
                        max={1000}
                      />
                      <Slider
                        value={[field.value]}
                        min={30}
                        max={1000}
                        step={1}
                        onValueChange={(vals) => field.onChange(vals[0])}
                        className="flex-1"
                      />
                    </div>
                  </FormControl>
                  <FormDescription>
                    Number of bars/candles to analyze (30-1000).
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="numIndicators"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Number of Indicators</FormLabel>
                  <FormControl>
                    <div className="flex items-center space-x-4">
                      <Input
                        type="number"
                        {...field}
                        className="w-24"
                        min={1}
                        max={10}
                      />
                      <Slider
                        value={[field.value]}
                        min={1}
                        max={10}
                        step={1}
                        onValueChange={(vals) => field.onChange(vals[0])}
                        className="flex-1"
                      />
                    </div>
                  </FormControl>
                  <FormDescription>
                    The number of technical indicators to include in each random strategy (1-10).
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="targetRoi"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Target ROI (%)</FormLabel>
                  <FormControl>
                    <div className="flex items-center space-x-4">
                      <Input
                        type="number"
                        {...field}
                        className="w-24"
                        step={0.1}
                        min={0.1}
                        max={10}
                      />
                      <Slider
                        value={[field.value]}
                        min={0.1}
                        max={10}
                        step={0.1}
                        onValueChange={(vals) => field.onChange(vals[0])}
                        className="flex-1"
                      />
                    </div>
                  </FormControl>
                  <FormDescription>
                    Target return-on-investment per trade (0.1-10%).
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <FormField
                control={form.control}
                name="useVolatilityScaling"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <div className="space-y-1 leading-none">
                      <FormLabel>Use Volatility Scaling</FormLabel>
                      <FormDescription>
                        Adjust position sizes based on market volatility.
                      </FormDescription>
                    </div>
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="includeSentiment"
                render={({ field }) => (
                  <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                    <FormControl>
                      <Checkbox
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <div className="space-y-1 leading-none">
                      <FormLabel>Include Sentiment Data</FormLabel>
                      <FormDescription>
                        Add market sentiment indicators to the analysis.
                      </FormDescription>
                    </div>
                  </FormItem>
                )}
              />
            </div>

            <Button type="submit" className="w-full" disabled={isSimulating}>
              {isSimulating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Running Simulation...
                </>
              ) : (
                'Run Simulation'
              )}
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}