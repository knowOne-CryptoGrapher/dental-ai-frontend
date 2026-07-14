import React from 'react';
import LandingNavbar from '../components/landing/LandingNavbar';
import LandingFooter from '../components/landing/LandingFooter';

const SECTIONS = [
  {
    title: '1. Acceptance of Terms',
    body: 'By accessing or using Dental AI, you agree to these Terms of Service. If you do not agree, do not use the service. If you are using Dental AI on behalf of a dental practice or organization, you represent that you are authorized to bind that organization to these terms.',
  },
  {
    title: '2. Description of Service',
    body: 'Dental AI provides an AI-powered dental receptionist platform, including voice AI, appointment management, insurance-related workflows, and practice analytics. The specific features available to you depend on your subscription plan and configuration.',
  },
  {
    title: '3. Subscription and Billing',
    body: 'Dental AI is offered on a subscription basis and billed monthly (or as otherwise agreed in writing). You may cancel at any time, and your subscription will remain active until the end of the current billing period. Refunds are not provided for partial billing periods. Plan upgrades or downgrades may take effect immediately and may change your billing amount on a pro-rated basis.',
  },
  {
    title: '3a. AI Technology Disclosure',
    body: 'Dental AI uses artificial intelligence to power the virtual receptionist experience. By using the service, you acknowledge and agree that:',
    bullets: [
      'The virtual receptionist is an AI, not a human. Callers are informed of this at the start of each call.',
      'AI responses are generated automatically and may occasionally be inaccurate, incomplete, or unsuitable for a specific situation. Your practice remains responsible for reviewing AI-generated data (such as appointment bookings, call summaries, and patient records) before acting on it.',
      'Calls are recorded and transcribed by our telephony provider (Retell AI). Transcripts are processed by AI language model providers (Anthropic, Groq) to generate responses. PHI redaction is applied before transmission to AI providers.',
      'Your practice is responsible for ensuring that appropriate notices, disclosures, and consents are provided to patients and callers in your jurisdiction regarding AI-assisted interactions and call recording.',
      'The AI does not provide medical or dental advice. Patients requiring clinical guidance must be directed to a qualified dental professional.',
    ],
  },
  {
    title: '4. Acceptable Use',
    body: 'You agree not to:',
    bullets: [
      'Use Dental AI in any way that violates applicable laws or regulations.',
      'Use the service to transmit unlawful, harmful, or abusive content.',
      'Attempt to gain unauthorized access to the service or related systems.',
      'Copy, modify, reverse-engineer, or create derivative works of the platform except as permitted by law.',
    ],
    body3: 'You are responsible for all activity under your account, including actions taken by your staff and authorized users. If you use call recording or AI-assisted interactions, you are responsible for ensuring that appropriate notices and consents are provided to patients and callers as required by applicable law in your jurisdiction.',
  },
  {
    title: '5. Data and Privacy',
    body: 'Your use of Dental AI is also governed by our Privacy Policy. You retain ownership of all practice and patient data that you input into the service or that is generated on your behalf. We do not sell your data.',
    body2: 'You grant us a limited license to use, store, process, and transmit your data as necessary to provide the service, maintain security, comply with law, and generate aggregated, de-identified analytics that do not identify you or your patients.',
  },
  {
    title: '6. Uptime and Support',
    body: 'We target 99.9% uptime for the core platform, excluding scheduled maintenance and events outside our reasonable control (such as force majeure or upstream provider outages). Scheduled maintenance will be communicated in advance where reasonably possible.',
    body2: 'Elite plan customers receive priority support with a 4-hour response service level target during business hours. Support for other plans is provided on a commercially reasonable efforts basis.',
  },
  {
    title: '7. No Warranties',
    body: 'Dental AI is provided on an "as-is" and "as-available" basis. To the maximum extent permitted by law, we disclaim all warranties, whether express, implied, or statutory, including any implied warranties of merchantability, fitness for a particular purpose, and non-infringement. We do not warrant that the service will be error-free, uninterrupted, or that it will meet your specific requirements.',
  },
  {
    title: '8. Limitation of Liability',
    body: 'To the maximum extent permitted by law, Dental AI is not liable for any indirect, incidental, special, consequential, or punitive damages, or for any loss of profits, revenue, data, or business opportunities, arising out of or related to your use of the service.',
    body2: 'Our total aggregate liability for any claims arising out of or related to the service is limited to the amount you paid for the service in the three (3) months immediately preceding the event giving rise to the claim.',
  },
  {
    title: '9. Indemnity',
    body: 'You agree to indemnify and hold harmless Dental AI, its officers, employees, and contractors from and against any claims, damages, losses, liabilities, and expenses (including reasonable legal fees) arising out of or related to: (a) your use of the service in violation of these terms or applicable law; (b) your failure to obtain required consents for call recording or AI-assisted interactions; or (c) any content or data you submit to the service.',
  },
  {
    title: '10. Termination',
    body: 'Either you or Dental AI may terminate the service at any time. Upon termination:',
    bullets: [
      'Your access to the service will be disabled at the end of the current billing period (unless terminated for cause).',
      'Your data will be retained for approximately 30 days, after which it will be deleted or anonymized from active systems and backups in accordance with our retention procedures, unless you request export or a different retention period consistent with applicable law and our Privacy Policy.',
    ],
  },
  {
    title: '11. Changes to the Service and Terms',
    body: 'We may update or modify the service from time to time, including adding or removing features. We may also update these Terms of Service. When we make material changes, we will update the "Last updated" date and, where appropriate, provide additional notice (for example, via email or in-app notification). Your continued use of the service after changes take effect constitutes acceptance of the updated terms.',
  },
  {
    title: '12. Governing Law and Venue',
    body: 'These terms are governed by the laws of the Province of British Columbia and the federal laws of Canada applicable therein. Any disputes arising out of or relating to these terms or the service will be resolved in the courts of British Columbia, unless otherwise agreed in writing.',
  },
  {
    title: '13. Contact',
    contact: { email: 'legal@dentalai.ca', label: 'For legal or contractual questions, contact:', org: 'Dental AI — Canada' },
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
          <p className="text-sm text-slate-500">Last updated: July 14, 2026 — v1.2</p>
        </div>
      </section>

      {/* CONTENT */}
      <section className="py-14">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="space-y-10">
            {SECTIONS.map(sec => (
              <div key={sec.title} className="space-y-3">
                <h2 className="text-xl font-semibold text-slate-900 mb-3">{sec.title}</h2>
                {sec.body && (
                  <p className="text-slate-600 leading-relaxed">{sec.body}</p>
                )}
                {sec.body2 && (
                  <p className="text-slate-600 leading-relaxed">{sec.body2}</p>
                )}
                {sec.bullets && (
                  <ul className="space-y-1.5">
                    {sec.bullets.map(b => (
                      <li key={b} className="flex items-start gap-2 text-slate-600 leading-relaxed">
                        <span className="mt-2 w-1.5 h-1.5 rounded-full bg-teal-500 shrink-0" />
                        <span>{b}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {sec.body3 && (
                  <p className="text-slate-600 leading-relaxed">{sec.body3}</p>
                )}
                {sec.contact && (
                  <div className="text-slate-600 leading-relaxed space-y-1">
                    {sec.contact.label && <p>{sec.contact.label}</p>}
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
