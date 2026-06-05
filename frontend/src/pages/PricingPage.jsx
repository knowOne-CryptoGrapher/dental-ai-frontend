import React from 'react';
import { Link } from 'react-router-dom';
import { Check, X, CreditCard, RefreshCw, Shield } from 'lucide-react';
import {
  Accordion, AccordionItem, AccordionTrigger, AccordionContent,
} from '../components/ui/accordian';
import LandingNavbar from '../components/landing/LandingNavbar';
import LandingFooter from '../components/landing/LandingFooter';

// ── Plan data (source: plans.py) ──────────────────────────────────────────────

const PLANS = [
  {
    id: 'basic',
    name: 'Basic',
    price: '$399',
    limits: { calls: '250', providers: '5', locations: '1', users: '5' },
    ctaLabel: 'Start Free Trial',
    ctaHref: '/signup',
  },
  {
    id: 'professional',
    name: 'Professional',
    price: '$599',
    badge: 'Most Popular',
    isPopular: true,
    limits: { calls: '750', providers: '15', locations: '5', users: '25' },
    ctaLabel: 'Start Free Trial',
    ctaHref: '/signup',
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: '$999',
    limits: { calls: '2,500', providers: '50', locations: '25', users: '200' },
    ctaLabel: 'Contact Sales',
    ctaHref: 'mailto:sales@dentalai.ca',
  },
  {
    id: 'elite',
    name: 'Elite',
    price: '$1,499',
    badge: 'Most Powerful',
    isElite: true,
    limits: { calls: '10,000', providers: '200', locations: '100', users: '1,000' },
    ctaLabel: 'Contact Sales',
    ctaHref: 'mailto:sales@dentalai.ca',
  },
];

// Features per plan — matches ComparePlansModal TABLE_ROWS (FEATURES section only)
const FEATURE_ROWS = [
  { label: 'Voice AI Calls',       basic: true,  pro: true,  ent: true,  elite: true  },
  { label: 'Appointments',         basic: true,  pro: true,  ent: true,  elite: true  },
  { label: 'Patients',             basic: true,  pro: true,  ent: true,  elite: true  },
  { label: 'Calendar',             basic: true,  pro: true,  ent: true,  elite: true  },
  { label: 'Call Logs',            basic: true,  pro: true,  ent: true,  elite: true  },
  { label: 'Audit Logs',           basic: true,  pro: true,  ent: true,  elite: true  },
  { label: 'Analytics',            basic: false, pro: true,  ent: true,  elite: true  },
  { label: 'Insurance / CDAnet',   basic: false, pro: true,  ent: true,  elite: true  },
  { label: 'Multi-Location',       basic: false, pro: true,  ent: true,  elite: true  },
  { label: 'Custom Voice',         basic: false, pro: false, ent: true,  elite: true  },
  { label: 'Knowledge Base',       basic: false, pro: false, ent: true,  elite: true  },
  { label: 'Routing Rules',        basic: false, pro: false, ent: true,  elite: true  },
  { label: 'Dedicated Support SLA',basic: false, pro: false, ent: false, elite: true  },
  { label: 'HIPAA / PIPEDA BAA',   basic: false, pro: false, ent: false, elite: true  },
  { label: 'Custom Model Selection',basic:false, pro: false, ent: false, elite: true  },
];

const PLAN_FEATURE_KEY = { basic: 'basic', professional: 'pro', enterprise: 'ent', elite: 'elite' };

// ── Full comparison table rows (source: ComparePlansModal TABLE_ROWS) ─────────

const TABLE_ROWS = [
  { type: 'section', label: 'CORE' },
  { label: 'Voice AI Calls', values: ['250', '750', '2,500', '10,000'] },
  { label: 'Providers',      values: ['5', '15', '50', '200'] },
  { label: 'Locations',      values: ['1', '5', '25', '100'] },
  { label: 'Users',          values: ['5', '25', '200', '1,000'] },
  { type: 'section', label: 'FEATURES' },
  { label: 'Appointments',       values: [true,  true,  true,  true]  },
  { label: 'Patients',           values: [true,  true,  true,  true]  },
  { label: 'Calendar',           values: [true,  true,  true,  true]  },
  { label: 'Audit Logs',         values: [true,  true,  true,  true]  },
  { label: 'Analytics',          values: [false, true,  true,  true]  },
  { label: 'Insurance / CDAnet', values: [false, true,  true,  true]  },
  { label: 'Multi-Location',     values: [false, true,  true,  true]  },
  { label: 'Custom Voice',       values: [false, false, true,  true]  },
  { label: 'Knowledge Base',     values: [false, false, true,  true]  },
  { label: 'Routing Rules',      values: [false, false, true,  true]  },
  { label: 'SIP Telephony',      values: [false, false, 'soon', 'soon'] },
  { type: 'section', label: 'ELITE EXCLUSIVE' },
  { label: 'Dedicated Support SLA',   values: [false, false, false, true] },
  { label: 'HIPAA / PIPEDA BAA',      values: [false, false, false, true] },
  { label: 'Custom Model Selection',  values: [false, false, false, true] },
];

const PLAN_COLS = [
  { id: 'basic',        name: 'Basic',        price: '$399'   },
  { id: 'professional', name: 'Professional', price: '$599'   },
  { id: 'enterprise',   name: 'Enterprise',   price: '$999'   },
  { id: 'elite',        name: 'Elite',        price: '$1,499' },
];

// ── FAQ data ──────────────────────────────────────────────────────────────────

const FAQS = [
  {
    q: 'Is there a free trial?',
    a: 'Yes — all plans include a 14-day free trial with full feature access. No credit card required to start.',
  },
  {
    q: 'Can I change plans later?',
    a: 'Absolutely. You can upgrade or downgrade your plan at any time from your billing dashboard. Changes take effect immediately.',
  },
  {
    q: 'What phone systems does Dental AI work with?',
    a: 'Dental AI works with any phone system that supports call forwarding. No hardware changes or new equipment needed.',
  },
  {
    q: 'Is my patient data secure?',
    a: 'Yes. Dental AI is built with HIPAA and PIPEDA compliance in mind — Canadian data residency, PHI redaction, audit logging, and SOC 2 security controls are standard on all plans.',
  },
  {
    q: 'What is CDAnet/iTRANS integration?',
    a: "CDAnet is the Canadian Dental Association's claims network. Dental AI integrates directly for real-time insurance eligibility checks and electronic claim submission, available on Professional plans and above.",
  },
  {
    q: 'How long does setup take?',
    a: 'Most practices are live within 48 hours. Our onboarding team handles configuration and your AI is trained on your practice protocols before go-live.',
  },
];

// ── Sub-components ────────────────────────────────────────────────────────────

function Cell({ value, isEliteCol }) {
  if (value === true) {
    return (
      <span className="flex justify-center">
        <Check className={`w-4 h-4 ${isEliteCol ? 'text-[#b8962f]' : 'text-teal-600'}`} aria-label="Included" />
      </span>
    );
  }
  if (value === false) {
    return (
      <span className="flex justify-center">
        <X className="w-4 h-4 text-slate-300" aria-label="Not included" />
      </span>
    );
  }
  if (value === 'soon') {
    return (
      <span className="flex justify-center">
        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-slate-100 text-slate-500">
          Soon
        </span>
      </span>
    );
  }
  return (
    <span className={`text-sm font-semibold ${isEliteCol ? 'text-[#b8962f]' : 'text-slate-700'}`}>
      {value}
    </span>
  );
}

function PlanCard({ plan }) {
  const fKey = PLAN_FEATURE_KEY[plan.id];
  const isMailto = plan.ctaHref?.startsWith('mailto:');

  const cardBorder = plan.isElite
    ? {}
    : plan.isPopular
    ? 'border-2 border-teal-600'
    : 'border border-slate-200';

  const ctaCls = plan.isElite
    ? 'block text-center py-2.5 px-4 rounded-md text-sm font-semibold text-white hover:opacity-90 transition-opacity'
    : plan.isPopular
    ? 'block text-center py-2.5 px-4 rounded-md text-sm font-semibold bg-teal-600 hover:bg-teal-700 text-white transition-colors'
    : 'block text-center py-2.5 px-4 rounded-md text-sm font-semibold border border-teal-600 text-teal-600 hover:bg-teal-50 transition-colors';

  return (
    <div
      className={`bg-white rounded-xl p-6 flex flex-col shadow-sm relative ${typeof cardBorder === 'string' ? cardBorder : ''}`}
      style={plan.isElite ? { border: '2px solid #D4AF37' } : {}}
    >
      {plan.badge && (
        <span
          className={`absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-[11px] font-semibold whitespace-nowrap ${plan.isElite ? 'text-white' : 'bg-teal-600 text-white'}`}
          style={plan.isElite ? { backgroundColor: '#D4AF37' } : {}}
        >
          {plan.badge}
        </span>
      )}

      <div className="mb-4">
        <h3 className={`text-lg font-bold mb-1 ${plan.isElite ? 'text-[#b8962f]' : 'text-slate-900'}`}>
          {plan.name}
        </h3>
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-bold text-slate-900">{plan.price}</span>
          <span className="text-sm text-slate-500">/mo</span>
        </div>
      </div>

      {/* Limits grid */}
      <div className={`grid grid-cols-2 gap-2 mb-5 p-3 rounded-lg ${plan.isElite ? 'bg-yellow-50/50' : 'bg-slate-50'}`}>
        {[
          { val: plan.limits.calls, label: 'calls/mo' },
          { val: plan.limits.providers, label: 'providers' },
          { val: plan.limits.locations, label: 'locations' },
          { val: plan.limits.users, label: 'users' },
        ].map(({ val, label }) => (
          <div key={label} className="text-center">
            <p className={`text-sm font-bold ${plan.isElite ? 'text-[#b8962f]' : 'text-slate-900'}`}>{val}</p>
            <p className="text-[11px] text-slate-500">{label}</p>
          </div>
        ))}
      </div>

      {/* Feature list */}
      <ul className="space-y-1.5 flex-1 mb-6">
        {FEATURE_ROWS.map(row => {
          const included = row[fKey];
          return (
            <li key={row.label} className="flex items-center gap-2">
              {included ? (
                <Check className={`w-3.5 h-3.5 shrink-0 ${plan.isElite ? 'text-[#D4AF37]' : 'text-teal-500'}`} />
              ) : (
                <X className="w-3.5 h-3.5 shrink-0 text-slate-300" />
              )}
              <span className={`text-xs ${included ? 'text-slate-700' : 'text-slate-400'}`}>{row.label}</span>
            </li>
          );
        })}
      </ul>

      {isMailto ? (
        <a href={plan.ctaHref} className={ctaCls} style={plan.isElite ? { backgroundColor: '#D4AF37' } : {}}>
          {plan.ctaLabel}
        </a>
      ) : (
        <Link to={plan.ctaHref} className={ctaCls}>
          {plan.ctaLabel}
        </Link>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-white">
      <LandingNavbar />

      {/* HERO */}
      <section className="bg-white py-16 border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h1 className="text-4xl sm:text-5xl font-bold text-slate-900 mb-4">
            Simple, transparent pricing
          </h1>
          <p className="text-lg text-slate-600 leading-relaxed max-w-2xl mx-auto mb-8">
            No setup fees. No long-term contracts. Cancel anytime. Choose the plan that fits your practice.
          </p>
          <div className="flex flex-col sm:flex-row justify-center gap-6">
            <div className="flex items-center gap-2 text-slate-600">
              <CreditCard className="w-4 h-4 text-teal-500 shrink-0" />
              <span className="text-sm">No setup fees</span>
            </div>
            <div className="flex items-center gap-2 text-slate-600">
              <RefreshCw className="w-4 h-4 text-teal-500 shrink-0" />
              <span className="text-sm">Cancel anytime</span>
            </div>
            <div className="flex items-center gap-2 text-slate-600">
              <Shield className="w-4 h-4 text-teal-500 shrink-0" />
              <span className="text-sm">HIPAA & PIPEDA Ready</span>
            </div>
          </div>
        </div>
      </section>

      {/* PLAN CARDS */}
      <section className="bg-slate-50 py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 items-start">
            {PLANS.map(plan => <PlanCard key={plan.id} plan={plan} />)}
          </div>
          <p className="text-center text-xs text-slate-400 mt-6">
            All plans billed monthly · Prices in CAD · 14-day free trial on all plans
          </p>
        </div>
      </section>

      {/* FULL COMPARISON TABLE */}
      <section className="bg-white py-16">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-2 text-center">Full feature comparison</h2>
          <p className="text-slate-500 text-sm text-center mb-10">Every feature, side by side.</p>

          <div className="overflow-x-auto rounded-xl border border-slate-200">
            <table className="w-full border-collapse min-w-[560px]">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="px-5 py-3.5 text-left w-44" />
                  {PLAN_COLS.map(plan => {
                    const isElite = plan.id === 'elite';
                    return (
                      <th
                        key={plan.id}
                        className={`px-4 py-3.5 text-center min-w-[110px] border-b-2 ${
                          isElite
                            ? 'bg-gradient-to-b from-yellow-50 to-slate-50 border-[#D4AF37]'
                            : 'border-slate-200'
                        }`}
                      >
                        <div className={`text-sm font-bold ${isElite ? 'text-[#b8962f]' : 'text-slate-900'}`}>
                          {plan.name}
                        </div>
                        <div className={`text-xs mt-0.5 ${isElite ? 'text-[#b8962f]' : 'text-slate-500'}`}>
                          {plan.price}<span className="font-normal text-slate-400">/mo</span>
                        </div>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {TABLE_ROWS.map(row => {
                  if (row.type === 'section') {
                    return (
                      <tr key={row.label} className="bg-slate-50/80">
                        <td
                          colSpan={5}
                          className="px-5 py-2 text-[10px] font-bold text-slate-400 uppercase tracking-widest"
                        >
                          {row.label}
                        </td>
                      </tr>
                    );
                  }
                  return (
                    <tr key={row.label} className="border-t border-slate-100 hover:bg-slate-50/30 transition-colors">
                      <td className="px-5 py-2.5 text-[13px] text-slate-700">{row.label}</td>
                      {row.values.map((val, colIdx) => {
                        const plan = PLAN_COLS[colIdx];
                        const isElite = plan.id === 'elite';
                        return (
                          <td
                            key={plan.id}
                            className={`px-4 py-2.5 text-center ${isElite ? 'bg-yellow-50/20' : ''}`}
                          >
                            <Cell value={val} isEliteCol={isElite} />
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="bg-slate-50 py-16">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-2xl font-bold text-slate-900 mb-8 text-center">
            Frequently asked questions
          </h2>
          <Accordion type="single" collapsible className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white overflow-hidden">
            {FAQS.map((faq, i) => (
              <AccordionItem key={i} value={`faq-${i}`} className="border-none px-6">
                <AccordionTrigger className="text-sm font-medium text-slate-900 hover:no-underline py-4">
                  {faq.q}
                </AccordionTrigger>
                <AccordionContent>
                  <p className="text-sm text-slate-600 leading-relaxed pb-1">{faq.a}</p>
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </section>

      {/* CTA BANNER */}
      <section className="bg-teal-600 py-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl font-bold text-white mb-4">Ready to get started?</h2>
          <p className="text-teal-100 text-lg leading-relaxed mb-8 max-w-xl mx-auto">
            Join dental practices across Canada.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link
              to="/signup"
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

      <LandingFooter />
    </div>
  );
}
