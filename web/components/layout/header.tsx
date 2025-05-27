'use client';

import Link from 'next/link';
import { useState } from 'react';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ThemeToggle } from '@/components/theme/theme-toggle';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Menu } from 'lucide-react';

const navigation = [
  { name: 'Home', href: '/' },
  { name: 'Dashboard', href: '/dashboard' },
  { name: 'Simulate', href: '/simulate' },
  { name: 'Pricing', href: '/pricing' },
];

export default function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const pathname = usePathname();

  return (
    <header className="bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-40 border-b">
      <nav className="mx-auto flex max-w-7xl items-center justify-between p-6 lg:px-8" aria-label="Global">
        <div className="flex lg:flex-1">
          <Link href="/" className="flex items-center space-x-2">
            <span className="font-mono font-bold text-xl">Quanticon</span>
          </Link>
        </div>
        
        <div className="flex lg:hidden">
          <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon">
                <Menu className="h-6 w-6" />
                <span className="sr-only">Open menu</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="w-[300px]">
              <div className="flex flex-col space-y-4 mt-6">
                {navigation.map((item) => (
                  <Link 
                    key={item.name} 
                    href={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={cn(
                      'px-3 py-2 text-lg font-medium rounded-md',
                      pathname === item.href 
                        ? 'text-primary bg-secondary' 
                        : 'text-muted-foreground hover:text-primary hover:bg-secondary/50'
                    )}
                  >
                    {item.name}
                  </Link>
                ))}
                <div className="mt-4 pt-4 border-t border-border">
                  <Link 
                    href="/login" 
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-2 text-lg font-medium rounded-md text-muted-foreground hover:text-primary hover:bg-secondary/50"
                  >
                    Sign in
                  </Link>
                  <Link 
                    href="/signup"
                    onClick={() => setMobileMenuOpen(false)}
                    className="block mt-2 w-full"
                  >
                    <Button className="w-full" size="lg">Sign up</Button>
                  </Link>
                </div>
              </div>
            </SheetContent>
          </Sheet>
        </div>
        
        <div className="hidden lg:flex lg:gap-x-8">
          {navigation.map((item) => (
            <Link 
              key={item.name} 
              href={item.href}
              className={cn(
                'px-3 py-2 text-sm font-medium rounded-md transition-colors',
                pathname === item.href 
                  ? 'text-primary bg-secondary' 
                  : 'text-muted-foreground hover:text-primary hover:bg-secondary/50'
              )}
            >
              {item.name}
            </Link>
          ))}
        </div>
        
        <div className="hidden lg:flex lg:flex-1 lg:justify-end lg:items-center">
          <ThemeToggle className="mr-4" />
          <Link href="/login" className="text-sm font-medium text-muted-foreground hover:text-primary mr-8">
            Sign in
          </Link>
          <Link href="/signup">
            <Button>Sign up</Button>
          </Link>
        </div>
      </nav>
    </header>
  );
}