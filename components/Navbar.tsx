import React, { useState } from 'react';

// Helper for hash-based router navigation (since this is SPA output request)
// In Next.js this would be <Link href="...">
interface NavLinkProps {
  href: string;
  children: React.ReactNode;
  active?: boolean;
}

const NavLink: React.FC<NavLinkProps> = ({ href, children, active }) => (
  <a 
    href={href}
    className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
      active 
        ? 'bg-surface text-primary border border-primary/20' 
        : 'text-gray-300 hover:bg-surface hover:text-white'
    }`}
  >
    {children}
  </a>
);

const Navbar: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <nav className="bg-background/95 backdrop-blur-sm border-b border-surface sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-8">
            <a href="#/" className="flex-shrink-0">
              <span className="text-2xl font-bold text-primary tracking-tighter">CINEMA<span className="text-white">WALL</span></span>
            </a>
            <div className="hidden md:block">
              <div className="ml-10 flex items-baseline space-x-4">
                <NavLink href="#/">Wall</NavLink>
                <NavLink href="#/news">News</NavLink>
                <NavLink href="#/vault">Vault</NavLink>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            {/* Search Bar - Visual only for Navbar, implemented in Page */}
            <div className="relative hidden sm:block">
              <input 
                type="text" 
                placeholder="Search movies..." 
                className="bg-surface text-sm text-white rounded-full pl-4 pr-10 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary w-64 border border-slate-700"
              />
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 absolute right-3 top-2 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
          </div>

          <div className="-mr-2 flex md:hidden">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              type="button"
              className="bg-surface inline-flex items-center justify-center p-2 rounded-md text-gray-400 hover:text-white hover:bg-gray-700 focus:outline-none"
            >
              <span className="sr-only">Open main menu</span>
              {mobileMenuOpen ? (
                <svg className="block h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="block h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      {mobileMenuOpen && (
        <div className="md:hidden bg-surface border-t border-slate-700">
          <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
            <a href="#/" className="text-gray-300 hover:text-white block px-3 py-2 rounded-md text-base font-medium">Wall</a>
            <a href="#/news" className="text-gray-300 hover:text-white block px-3 py-2 rounded-md text-base font-medium">News</a>
            <a href="#/vault" className="text-gray-300 hover:text-white block px-3 py-2 rounded-md text-base font-medium">Vault</a>
          </div>
        </div>
      )}
    </nav>
  );
};

export default Navbar;