import React from 'react';
import LandingNavbar from '../components/landing/LandingNavbar';
import LandingFooter from '../components/landing/LandingFooter';

const SECTIONS = [
  {
    title: '1. Introduction',
    body: 'Dental AI ("we", "us", "our") is committed to protecting your privacy. This policy explains how we collect, use, and protect personal and health information in accordance with the Personal Information Protection and Electronic Documents Act (PIPEDA) and the BC Personal Information Protection Act (PIPA).',
  },
  {
    title: '2. Information We Collect',
    bullets: [
      'Practice information (name, address, contact details)',
      'Patient interaction data processed through our AI (call recordings, transcripts, appointment requests)',
      'Billing and payment information',
      'Usage data and analytics',
    ],
  },
  {
    title: '3. How We Use Your Information',
    bullets: [
      'To provide and improve our AI receptionist service',
      'To process insurance verification and claims',
      'To generate analytics and reporting',
      'To communicate with you about your account',
    ],
  },
  {
    title: '4. Data Residency',
    body: 'All Canadian customer data is stored in Canadian data centers (ca-west or ca-east regions). Data does not leave Canada without explicit consent.',
  },
  {
    title: '5. PHI Protection',
    body: 'Patient health information (PHI) is handled in accordance with HIPAA and PIPEDA requirements. PHI is redacted from logs, never used for model training, and retained only for the period specified in your data retention settings.',
  },
  {
    title: '6. Data Retention',
    body: 'You control your data retention period from your practice dashboard (default: 7 years, in line with Canadian dental record requirements). You may request deletion at any time by contacting support.',
  },
  {
    title: '7. Third-Party Services',
    body: 'Dental AI integrates with: Retell AI (voice processing), Stripe (billing), MongoDB Atlas (data storage), Google Cloud (infrastructure). Each provider is bound by appropriate data processing agreements.',
  },
  {
    title: '8. Your Rights',
    body: 'Under PIPEDA, you have the right to access, correct, and request deletion of your personal information. Contact us at privacy@dentalai.ca to exercise these rights.',
  },
  {
    title: '9. Contact',
    body: null,
    contact: { email: 'privacy@dentalai.ca', org: 'Dental AI — Canada' },
  },
];

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-white">
      <LandingNavbar />

      {/* HERO */}
      <section className="bg-slate-50 border-b border-slate-200 py-14">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="text-4xl font-bold text-slate-900 mb-2">Privacy Policy</h1>
          <p className="text-sm text-slate-500">Last updated: June 2026</p>
        </div>
      </section>

      {/* CONTENT */}
      <section className="py-14">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="prose-section space-y-10">
            {SECTIONS.map(sec => (
              <div key={sec.title}>
                <h2 className="text-xl font-semibold text-slate-900 mb-3">{sec.title}</h2>
                {sec.body && (
                  <p className="text-slate-600 leading-relaxed">{sec.body}</p>
                )}
                {sec.bullets && (
                  <ul className="space-y-1.5 mt-1">
                    {sec.bullets.map(b => (
                      <li key={b} className="flex items-start gap-2 text-slate-600 leading-relaxed">
                        <span className="mt-2 w-1.5 h-1.5 rounded-full bg-teal-500 shrink-0" />
                        <span>{b}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {sec.contact && (
                  <div className="text-slate-600 leading-relaxed space-y-1">
                    <p>
                      Privacy Officer:{' '}
                      <a href={`mailto:${sec.contact.email}`} className="text-teal-600 hover:underline">
                        {sec.contact.email}
                      </a>
                    </p>
                    <p>{sec.contact.org}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      <LandingFooter />
    </div>
  );
}
