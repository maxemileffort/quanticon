# Quanticon

Monte Carlo your way to smarter trades by simulating randomized strategies over technical indicators.

## Overview

Quanticon is a web application that helps traders discover profitable strategies through Monte Carlo simulations. By randomly combining technical indicators and their parameters, users can explore the vast universe of trading possibilities and identify strategies with strong risk-adjusted returns.

## Features

- **Monte Carlo Simulations**: Generate and test thousands of random strategy combinations
- **Technical Indicators**: finta (used in local version), evaluating options for main app
- **Performance Analytics**: Evaluate strategies using industry-standard metrics
- **Interactive Visualizations**: Analyze equity curves and trade distributions
- **Strategy Management**: Save and compare your best-performing strategies

## Tech Stack

- **Frontend**: Next.js 13 with App Router
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui
- **Charts**: Recharts
- **Technical Indicators**: finta (used in local version), evaluating options for main app
- **Authentication**: Email/Password (planned)
- **Database**: PostgreSQL via Supabase (planned)
- **Hosting**: Netlify

## Getting Started

1. Clone the repository
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
4. Open [http://localhost:3000](http://localhost:3000)

## Project Structure

```
├── app/                    # Next.js app directory
│   ├── dashboard/         # Dashboard page
│   ├── results/          # Simulation results pages
│   ├── simulate/         # New simulation page
│   └── layout.tsx        # Root layout
├── components/            # React components
│   ├── dashboard/        # Dashboard-specific components
│   ├── landing/          # Landing page components
│   ├── layout/           # Layout components
│   ├── results/          # Results page components
│   ├── simulation/       # Simulation form components
│   ├── theme/           # Theme components
│   └── ui/              # Reusable UI components
└── lib/                  # Utility functions
```

## Development

- Uses Next.js 13 with App Router for server components
- Follows a component-based architecture
- Implements responsive design principles
- Features dark mode by default

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request

## License

MIT
