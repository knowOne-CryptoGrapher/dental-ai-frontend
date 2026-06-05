import React from 'react';
import LandingNavbar from '../components/landing/LandingNavbar';
import LandingFooter from '../components/landing/LandingFooter';

const SECTIONS = [
  {
    title: '1. Acceptance of Terms',
    body: 'By using Dental AI, you agree to these Terms of Service. If you do not agree, do not use the service.',
  },
  {
    title: '2. Description of Service',
    body: 'Dental AI provides an AI-powered dental receptionist platform including voice AI, appointment management, insurance verification, and practice analytics.',
  },
  {
    title: '3. Subscription and Billing',
    body: 'Services are billed monthly. You may cancel at any time. Refunds are not provided for partial billing periods. Plan changes take effect immediately.',
  },
  {
    title: '4. Acceptable Use',
    body: 'You may not use Dental AI to violate any law, transmit harmful content, or attempt to reverse-engineer the platform. You are responsible for all activity under your account.',
  },
  {
    title: '5. Data and Privacy',
    body: 'Your use of Dental AI is also governed by our Privacy Policy. You retain ownership of all practice and patient data. We do not sell your data.',
  },
  {
    title: '6. Uptime and Support',
    body: 'We target 99.9% uptime. Scheduled maintenance will be communicated in advance. Elite plan customers receive priority support with a 4-hour response SLA.',
  },
  {
    title: '7. Limitation of Liability',
    body: 'Dental AI is not liable for indirect or consequential damages. Our total liability is limited to the amount paid in the prior 3 months.',
  },
  {
    title: '8. Termination',
    body: 'Either party may terminate at any time. Upon termination, your data is retained for 30 days then deleted unless export is requested.',
  },
  {
    title: '9. Governing Law',
    body: 'These terms are governed by the laws of British Columbia, Canada.',
  },
  {
    title: '10. Contact',
    contact: { email: 'legal@dentalai.ca', org: 'Dental AI — Canada' },
  },
];

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen bg-white">
      <LandingNavbar />

      {/* HERO */}
      <section className="bg-slate-50 border-b border-slate-200 py-14">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <h1 className="text-4xl font-bold text-slate-900 mb-2">Terms of Service</h1>
          <p className="text-sm text-slate-500">Last updated: June 2026</p>
        </div>
      </section>

      {/* CONTENT */}
      <section className="py-14">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="space-y-10">
            {SECTIONS.map(sec => (
              <div key={sec.title}>
                <h2 className="text-xl font-semibold text-slate-900 mb-3">{sec.title}</h2>
                {sec.body && (
                  <p className="text-slate-600 leading-relaxed">{sec.body}</p>
                )}
                {sec.contact && (
                  <div className="text-slate-600 leading-relaxed space-y-1">
                    <p>
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
