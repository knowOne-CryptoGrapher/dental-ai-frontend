import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Phone, ShieldCheck, Globe, MapPin, BarChart2, Menu, X, ChevronRight } from 'lucide-react';
import FeatureCard from '../components/landing/FeatureCard';
import TestimonialCard from '../components/landing/TestimonialCard';
import PricingPreviewCard from '../components/landing/PricingPreviewCard';
import StepCard from '../components/landing/StepCard';
import ContactSalesModal from '../components/sales/ContactSalesModal';
import FoundingClinicBanner from '../components/sales/FoundingClinicBanner';

const FEATURES = [
  {
    icon: Phone,
    title: 'AI Phone Receptionist',
    description:
      'Answers every call 24/7 with a natural, clinic-trained voice. Handles appointment booking, rescheduling, and patient inquiries without hold times.',
  },
  {
    icon: ShieldCheck,
    title: 'Insurance Verification & CDAnet',
    description:
      'Real-time eligibility checks and CDAnet/iTRANS claim integration. Reduce claim rejections and speed up reimbursements.',
  },
  {
    icon: MapPin,
    title: 'Multi-Location Ready',
    description:
      'Manage multiple clinic locations from a single dashboard. Route calls, track performance, and coordinate patient flow across your entire practice network.',
  },
  {
    icon: BarChart2,
    title: 'Practice Analytics',
    description:
      'Track call volume, appointment conversion rates, provider utilization, and patient trends — all in one real-time dashboard.',
  },
];

const STEPS = [
  {
    number: '01',
    title: 'Connect Your Phone System',
    description:
      'Forward your existing clinic number to Dental AI. Works with any phone provider — no hardware changes needed.',
  },
  {
    number: '02',
    title: 'Train on Your Practice',
    description:
      "Upload your protocols, insurance policies, and FAQs. Your AI learns your clinic's specific workflows and terminology.",
  },
  {
    number: '03',
    title: 'Go Live Instantly',
    description:
      'Your AI receptionist starts answering calls immediately. Monitor every interaction from your dashboard in real time.',
  },
];

const PLANS = [
  {
    name: 'Basic',
    price: '$399',
    compliance: 'PHI-safe, PIPEDA/PIPA compliant',
    features: ['250 calls/mo', '5 providers', '1 location', 'Voice AI', 'Appointments', 'Audit Logs'],
    ctaLabel: 'Get Started',
    ctaHref: '/signup?plan=basic',
  },
  {
    name: 'Professional',
    price: '$599',
    badge: 'Most Popular',
    isPopular: true,
    features: ['750 calls/mo', '15 providers', '5 locations', 'Everything in Basic', 'Analytics', 'Insurance/CDAnet'],
    ctaLabel: 'Get Started',
    ctaHref: '/signup?plan=professional',
  },
  {
    name: 'Enterprise',
    price: '$999',
    features: ['2,500 calls/mo', '50 providers', '25 locations', 'Everything in Professional', 'Knowledge Base', 'Routing Rules'],
    ctaLabel: 'Contact Sales',
    ctaHref: '/contact-sales?plan=enterprise',
  },
  {
    name: 'Elite',
    price: '$1,499',
    badge: 'Most Powerful',
    isElite: true,
    compliance: 'Signed HIPAA/PIPEDA BAA included',
    features: [
      '10,000 calls/mo',
      '200 providers',
      '100 locations',
      'Everything in Enterprise',
      'Dedicated Support SLA',
      'HIPAA/PIPEDA BAA',
      'Custom Model Selection',
    ],
    ctaLabel: 'Contact Sales',
    ctaHref: '/contact-sales?plan=elite',
  },
];

const TESTIMONIALS = [
  {
    quote:
      'Dental AI handles over 80% of our incoming calls without any staff involvement. Our front desk team now focuses entirely on in-clinic patients.',
    name: 'Dr. Sarah Mitchell',
    title: 'Owner',
    clinic: 'Mitchell Family Dental, Vancouver BC',
  },
  {
    quote:
      'The insurance verification alone saves us 2–3 hours per day. CDAnet integration was seamless and our claim rejection rate dropped immediately.',
    name: 'Dr. James Okafor',
    title: 'Practice Manager',
    clinic: 'Okafor Dental Group, Toronto ON',
  },
  {
    quote:
      'We run four locations and Dental AI gives us one unified view of everything. Routing rules let us customize how each location handles after-hours calls.',
    name: 'Dr. Priya Sharma',
    title: 'Clinical Director',
    clinic: 'Sharma Dental Network, Calgary AB',
  },
];

export default function LandingPage() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [salesModal, setSalesModal] = useState({ open: false, plan: 'enterprise' });

  return (
    <div className="min-h-screen bg-white">
      <FoundingClinicBanner />
      {/* ── NAVBAR ── */}
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
                to="/pricing"
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
                to="/pricing"
                className="block bg-teal-600 hover:bg-teal-700 text-white text-sm font-semibold px-4 py-2.5 rounded-md transition-colors text-center"
                onClick={() => setMobileOpen(false)}
              >
                Start Free Trial
              </Link>
            </div>
          )}
        </div>
      </nav>

      {/* ── HERO ── */}
      <section className="bg-white py-20 lg:py-28">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
            <div>
              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-slate-900 leading-tight mb-6">
                Your 24/7 AI Dental Receptionist
              </h1>
              <p className="text-lg text-slate-600 leading-relaxed max-w-xl mb-8">
                Answering calls, booking appointments, verifying insurance, and managing patient flow — automatically.
              </p>
              <div className="flex flex-col sm:flex-row gap-3 mb-10">
                <Link
                  to="/pricing"
                  className="bg-teal-600 hover:bg-teal-700 text-white font-semibold px-6 py-3 rounded-md transition-colors text-center text-sm"
                >
                  Start Free Trial
                </Link>
                <Link
                  to="/demo"
                  className="border border-teal-600 text-teal-600 hover:bg-teal-50 font-semibold px-6 py-3 rounded-md transition-colors text-center text-sm"
                >
                  Book a Demo
                </Link>
              </div>
              <div className="flex flex-col sm:flex-row gap-5">
                <div className="flex items-center gap-2 text-slate-500">
                  <ShieldCheck className="w-4 h-4 text-teal-500 shrink-0" />
                  <span className="text-sm">HIPAA & PIPEDA Ready</span>
                </div>
                <div className="flex items-center gap-2 text-slate-500">
                  <Phone className="w-4 h-4 text-teal-500 shrink-0" />
                  <span className="text-sm">Powered by Retell AI</span>
                </div>
                <div className="flex items-center gap-2 text-slate-500">
                  <Globe className="w-4 h-4 text-teal-500 shrink-0" />
                  <span className="text-sm">Canadian Data Residency</span>
                </div>
              </div>
            </div>

            {/* Hero illustration */}
            <div className="hidden lg:flex items-center justify-center">
              <div className="w-full max-w-md h-80 bg-teal-50 rounded-2xl border border-teal-100 flex flex-col items-center justify-center gap-5 px-8">
                <div className="flex items-center gap-3 bg-white rounded-xl px-5 py-3 shadow-sm border border-teal-100 w-full">
                  <div className="w-10 h-10 bg-teal-100 rounded-full flex items-center justify-center shrink-0">
                    <Phone className="w-5 h-5 text-teal-600" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-slate-800">AI Receptionist</p>
                    <p className="text-xs text-teal-600">Answering call...</p>
                  </div>
                  <div className="flex items-end gap-0.5 h-6">
                    {[0.4, 0.75, 1, 0.55, 0.85, 0.6, 0.9, 0.45].map((h, i) => (
                      <div
                        key={i}
                        className="w-1 bg-teal-400 rounded-full"
                        style={{ height: `${h * 24}px` }}
                      />
                    ))}
                  </div>
                </div>

                <svg width="220" height="44" viewBox="0 0 220 44" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M0 22 Q13.75 4 27.5 22 Q41.25 40 55 22 Q68.75 4 82.5 22 Q96.25 40 110 22 Q123.75 4 137.5 22 Q151.25 40 165 22 Q178.75 4 192.5 22 Q206.25 40 220 22"
                    stroke="#0d9488"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    opacity="0.45"
                  />
                </svg>

                <div className="grid grid-cols-3 gap-3 w-full">
                  {[
                    { label: 'Calls Today', value: '47' },
                    { label: 'Booked', value: '12' },
                    { label: 'Resolved', value: '94%' },
                  ].map(({ label, value }) => (
                    <div key={label} className="bg-white rounded-lg p-2.5 text-center border border-teal-100">
                      <p className="text-base font-bold text-teal-700">{value}</p>
                      <p className="text-[10px] text-slate-500 mt-0.5">{label}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── FEATURES ── */}
      <section className="bg-slate-50 py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">
              Everything your front desk does — handled automatically
            </h2>
            <p className="text-slate-600 max-w-2xl mx-auto leading-relaxed">
              Dental AI answers every call, qualifies patients, books appointments, and verifies insurance without lifting a finger.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {FEATURES.map((f) => (
              <FeatureCard key={f.title} icon={f.icon} title={f.title} description={f.description} />
            ))}
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ── */}
      <section className="bg-white py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-14">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">Up and running in 48 hours</h2>
            <p className="text-slate-600 max-w-xl mx-auto leading-relaxed">
              No hardware. No IT team. Just connect your phone system and go live.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-10 relative">
            <div
              className="hidden md:block absolute h-px bg-teal-100 top-7"
              style={{ left: '22%', right: '22%' }}
            />
            {STEPS.map((s) => (
              <StepCard key={s.number} number={s.number} title={s.title} description={s.description} />
            ))}
          </div>
        </div>
      </section>

      {/* ── PRICING PREVIEW ── */}
      <section className="bg-slate-50 py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">Simple, transparent pricing</h2>
            <p className="text-slate-600 leading-relaxed">
              Choose the plan that fits your practice. Upgrade anytime as you grow.
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-6 items-start">
            {PLANS.map((plan) => (
              <PricingPreviewCard
                key={plan.name}
                name={plan.name}
                price={plan.price}
                badge={plan.badge}
                features={plan.features}
                ctaLabel={plan.ctaLabel}
                ctaHref={plan.ctaHref}
                onCtaClick={
                  plan.ctaHref?.startsWith('/contact-sales')
                    ? () => setSalesModal({ open: true, plan: plan.name.toLowerCase() })
                    : undefined
                }
                isElite={plan.isElite}
                isPopular={plan.isPopular}
                compliance={plan.compliance}
              />
            ))}
          </div>
          <div className="text-center mt-8">
            <Link
              to="/pricing"
              className="inline-flex items-center gap-1 text-teal-600 hover:text-teal-700 font-medium text-sm transition-colors"
            >
              See full pricing comparison
              <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* ── TESTIMONIALS ── */}
      <section className="bg-white py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold text-slate-900 mb-4">
              Trusted by dental practices across Canada
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {TESTIMONIALS.map((t) => (
              <TestimonialCard
                key={t.name}
                quote={t.quote}
                name={t.name}
                title={t.title}
                clinic={t.clinic}
              />
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA BANNER ── */}
      <section className="bg-teal-600 py-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">
            Ready to transform your front desk?
          </h2>
          <p className="text-teal-100 text-lg leading-relaxed mb-8 max-w-2xl mx-auto">
            Join dental practices across Canada using Dental AI to handle calls, bookings, and insurance — around the clock.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              to="/pricing"
              className="border-2 border-white text-white hover:bg-white hover:text-teal-600 font-semibold px-6 py-3 rounded-md transition-colors text-sm"
            >
              Start Free Trial
            </Link>
            <Link
              to="/demo"
              className="border-2 border-white text-white hover:bg-white hover:text-teal-600 font-semibold px-6 py-3 rounded-md transition-colors text-sm"
            >
              Book a Demo
            </Link>
          </div>
        </div>
      </section>

      <ContactSalesModal
        isOpen={salesModal.open}
        onClose={() => setSalesModal(m => ({ ...m, open: false }))}
        requestedPlan={salesModal.plan}
      />

      {/* ── FOOTER ── */}
      <footer className="bg-slate-900 py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div>
              <p className="text-xl font-bold text-white mb-2">Dental AI</p>
              <p className="text-sm text-slate-400 mb-4 leading-relaxed">
                Clinical-grade AI for modern dental practices
              </p>
              <p className="text-xs text-slate-500">© 2026 Dental AI. All rights reserved.</p>
            </div>
            <div>
              <p className="text-sm font-semibold text-white mb-3">Product</p>
              <ul className="space-y-2">
                <li>
                  <Link to="/pricing" className="text-sm text-slate-400 hover:text-white transition-colors">
                    Pricing
                  </Link>
                </li>
                <li>
                  <Link to="/login" className="text-sm text-slate-400 hover:text-white transition-colors">
                    Login
                  </Link>
                </li>
                <li>
                  <Link to="/signup" className="text-sm text-slate-400 hover:text-white transition-colors">
                    Sign Up
                  </Link>
                </li>
              </ul>
            </div>
            <div>
              <p className="text-sm font-semibold text-white mb-3">Company</p>
              <ul className="space-y-2">
                <li>
                  <Link to="/privacy" className="text-sm text-slate-400 hover:text-white transition-colors">
                    Privacy Policy
                  </Link>
                </li>
                <li>
                  <Link to="/terms" className="text-sm text-slate-400 hover:text-white transition-colors">
                    Terms of Service
                  </Link>
                </li>
                <li>
                  <a href="mailto:sales@dentalai.ca" className="text-sm text-slate-400 hover:text-white transition-colors">
                    Contact
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
