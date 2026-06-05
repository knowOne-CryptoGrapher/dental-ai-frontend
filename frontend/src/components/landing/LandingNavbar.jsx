import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Menu, X } from 'lucide-react';

export default function LandingNavbar() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <nav className="sticky top-0 z-50 bg-white border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link to="/" className="text-xl font-bold text-teal-600 tracking-tight">
            Dental AI
          </Link>

          <div className="hidden md:flex items-center gap-6">
            <Link to="/pricing" className="text-sm font-medium text-slate-600 hover:text-teal-600 transition-colors">
              Pricing
            </Link>
            <Link to="/login" className="text-sm font-medium text-slate-600 hover:text-teal-600 transition-colors">
              Login
            </Link>
            <Link
              to="/signup"
              className="bg-teal-600 hover:bg-teal-700 text-white text-sm font-semibold px-4 py-2 rounded-md transition-colors"
            >
              Start Free Trial
            </Link>
          </div>

          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden p-2 text-slate-600 hover:text-teal-600 transition-colors"
            aria-label="Toggle navigation"
          >
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {mobileOpen && (
          <div className="md:hidden py-4 border-t border-slate-100 space-y-3">
            <Link
              to="/pricing"
              className="block text-sm font-medium text-slate-700 hover:text-teal-600 transition-colors px-1"
              onClick={() => setMobileOpen(false)}
            >
              Pricing
            </Link>
            <Link
              to="/login"
              className="block text-sm font-medium text-slate-700 hover:text-teal-600 transition-colors px-1"
              onClick={() => setMobileOpen(false)}
            >
              Login
            </Link>
            <Link
              to="/signup"
              className="block bg-teal-600 hover:bg-teal-700 text-white text-sm font-semibold px-4 py-2.5 rounded-md transition-colors text-center"
              onClick={() => setMobileOpen(false)}
            >
              Start Free Trial
            </Link>
          </div>
        )}
      </div>
    </nav>
  );
}
