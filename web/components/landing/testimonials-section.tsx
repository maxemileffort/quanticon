import Image from 'next/image';

const testimonials = [
  {
    body: 'Quanticon saved me countless hours of backtesting. I found a strategy with a 1.8 Sharpe ratio in just 30 minutes!',
    author: {
      name: 'Sarah Johnson',
      handle: 'Hedge Fund Analyst',
      imageUrl: 'https://images.pexels.com/photos/733872/pexels-photo-733872.jpeg?auto=compress&cs=tinysrgb&w=800',
    },
  },
  {
    body: 'The randomized approach to strategy discovery helped me find combinations of indicators I would have never thought to try together.',
    author: {
      name: 'Michael Chen',
      handle: 'Retail Trader',
      imageUrl: 'https://images.pexels.com/photos/220453/pexels-photo-220453.jpeg?auto=compress&cs=tinysrgb&w=800',
    },
  },
  {
    body: 'As a quant developer, I appreciate how Quanticon handles the complexity of Monte Carlo simulations while keeping the interface simple.',
    author: {
      name: 'David Rodriguez',
      handle: 'Quantitative Developer',
      imageUrl: 'https://images.pexels.com/photos/2379005/pexels-photo-2379005.jpeg?auto=compress&cs=tinysrgb&w=800',
    },
  },
];

export default function TestimonialsSection() {
  return (
    <div id="testimonials" className="bg-background py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl lg:text-center">
          <h2 className="text-base font-semibold leading-7 text-chart-1">Testimonials</h2>
          <p className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">
            Trusted by traders worldwide
          </p>
          <p className="mt-6 text-lg leading-8 text-muted-foreground">
            Hear from traders and analysts who have found their edge with Quanticon.
          </p>
        </div>
        <div className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-6 sm:mt-20 lg:mx-0 lg:max-w-none lg:grid-cols-3">
          {testimonials.map((testimonial, i) => (
            <div
              key={i}
              className="flex flex-col justify-between rounded-2xl bg-card p-6 shadow-md ring-1 ring-border"
            >
              <div>
                <p className="text-base text-muted-foreground leading-7">{testimonial.body}</p>
              </div>
              <div className="mt-6 flex items-center gap-x-4">
                <Image
                  className="h-10 w-10 rounded-full bg-gray-50"
                  src={testimonial.author.imageUrl}
                  alt=""
                  width={40}
                  height={40}
                />
                <div>
                  <h3 className="text-sm font-semibold">{testimonial.author.name}</h3>
                  <p className="text-xs text-muted-foreground">{testimonial.author.handle}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}