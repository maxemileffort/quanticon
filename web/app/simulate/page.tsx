import { Metadata } from 'next';
import SimulationForm from '@/components/simulation/simulation-form';

export const metadata: Metadata = {
  title: 'New Simulation | Quanticon',
  description: 'Configure and run a new Monte Carlo trading simulation.',
};

export default function SimulatePage() {
  return (
    <div className="container max-w-4xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2">New Simulation</h1>
        <p className="text-muted-foreground">
          Configure the parameters for your Monte Carlo trading strategy simulation.
        </p>
      </div>
      
      <SimulationForm />
    </div>
  );
}