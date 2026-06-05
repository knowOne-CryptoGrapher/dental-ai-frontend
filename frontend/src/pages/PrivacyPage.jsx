import React from 'react';
import LandingNavbar from '../components/landing/LandingNavbar';
import LandingFooter from '../components/landing/LandingFooter';

const SECTIONS = [
  {
    title: '1. Introduction',
    body: 'Dental AI (“we”, “us”, “our”) provides an AI-powered receptionist platform for dental practices. We are committed to protecting privacy and handling personal information in accordance with the Personal Information Protection and Electronic Documents Act (PIPEDA) and the BC Personal Information Protection Act (PIPA). This policy explains how we collect, use, disclose, and protect personal and health information.',
    body2: 'For most practice and patient data, we act as a service provider / processor to dental practices, who remain responsible for their own compliance obligations and for providing any required notices and consents to their patients.',
  },
  {
    title: '2. Information We Collect',
    body: 'We may collect and process the following types of information:',
    bullets: [
      'Practice information: Name, address, contact details, plan and subscription details.',
      'User information: Names, roles, and contact details of staff users.',
      'Patient interaction data: Call recordings, transcripts, appointment requests, messages, and related metadata processed through our AI receptionist.',
      'Billing and payment information: Limited payment details processed via our payment provider (e.g., Stripe).',
      'Usage data and analytics: Log data, device information, IP addresses, timestamps, and feature usage to operate and improve the service.',
    ],
    body3: 'We collect this information directly from you, from your authorized users, and from integrated systems (e.g., telephony providers, practice management systems) as configured by your practice.',
  },
  {
    title: '3. How We Use Your Information',
    body: 'We use personal information to:',
    bullets: [
      'Provide, operate, and improve our AI receptionist and related services.',
      'Process appointment scheduling, reminders, and patient communications as configured by your practice.',
      'Support insurance verification and claims workflows where enabled.',
      'Generate practice-level analytics and reporting.',
      'Provide customer support and communicate with you about your account, security, and service updates.',
      'Meet our legal, regulatory, and security obligations.',
    ],
    body3: 'We do not sell your personal information.',
  },
  {
    title: '4. Data Residency',
    body: 'For Canadian customers, practice and patient data are stored in Canadian data centers (e.g., ca-west or ca-east regions). Our goal is to keep your data in Canada. Where limited cross-border access is required by our infrastructure or service providers (for example, for support or failover), it is governed by appropriate data protection agreements and safeguards.',
  },
  {
    title: '5. PHI Protection and Model Use',
    body: 'Patient health information (PHI) is handled in accordance with applicable health privacy requirements, including PIPEDA and relevant provincial laws. In particular:',
    bullets: [
      'PHI is redacted from application logs wherever technically feasible.',
      'PHI is not used to train our own models beyond what is necessary to provide the service you have requested.',
      'We require our AI and infrastructure providers to process PHI only as needed to deliver the service and to prohibit use of PHI for their own independent model training, subject to their published terms and our data processing agreements.',
      'Access to PHI is restricted to authorized personnel with a need to know and is protected by technical and organizational safeguards.',
    ],
  },
  {
    title: '6. Data Retention',
    body: 'You control your data retention period from your practice dashboard (default: 7 years, in line with common Canadian dental record retention expectations). After the configured retention period, data is deleted or anonymized from active systems and backups in accordance with our retention procedures.',
    body2: 'You may request deletion of specific data or your account at any time by contacting support, subject to any legal or regulatory retention requirements that apply to you as a health care provider.',
  },
  {
    title: '7. Third-Party Services',
    body: 'Dental AI integrates with third-party service providers, including:',
    bullets: [
      'Retell AI (voice processing and telephony)',
      'Stripe (billing and payments)',
      'MongoDB Atlas (database and data storage)',
      'Google Cloud (infrastructure and hosting)',
    ],
    body3: 'These providers act as our processors or sub-processors and are bound by appropriate data processing and security agreements. We only share the minimum necessary information with them to provide the service, and we do not permit them to use your data for their own marketing or unrelated purposes.',
  },
  {
    title: '8. Your Rights',
    body: 'Under PIPEDA and applicable provincial laws, you may have the right to:',
    bullets: [
      'Access the personal information we hold about you.',
      'Request correction of inaccurate or incomplete information.',
      'Request deletion of your personal information, subject to legal and contractual limitations.',
      'Withdraw consent to certain uses of your information, where consent is the basis for processing.',
    ],
    body3: 'To exercise these rights, contact us at privacy@dentalai.ca. For patient data, we may direct you to contact your dental practice, who is typically the controller of that information.',
  },
  {
    title: '9. Children and Minors',
    body: 'Dental AI is designed for use by dental practices and their authorized staff, not by patients or minors directly. Any information about minors is processed on behalf of the dental practice in the course of providing care.',
  },
  {
    title: '10. Security',
    body: 'We use reasonable physical, technical, and administrative safeguards to protect personal information, including encryption in transit, access controls, and audit logging. No system is perfectly secure, but we work continuously to improve our security posture.',
  },
  {
    title: '11. Changes to This Policy',
    body: 'We may update this Privacy Policy from time to time. When we do, we will update the “Last updated” date and, where appropriate, provide additional notice (for example, via email or in-app notification). Your continued use of the service after changes take effect constitutes acceptance of the updated policy.',
  },
  {
    title: '12. Contact',
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
