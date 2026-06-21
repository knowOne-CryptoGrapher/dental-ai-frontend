import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Clock, ShieldCheck } from 'lucide-react';
import LandingNavbar from '../components/landing/LandingNavbar';
import LandingFooter from '../components/landing/LandingFooter';
import SalesLeadForm from '../components/sales/SalesLeadForm';
import CrispChatPanel from '../components/sales/CrispChatPanel';

export default function ContactSalesPage() {
  const [searchParams] = useSearchParams();
  const requestedPlan = searchParams.get('plan') === 'elite' ? 'elite' : 'enterprise';
  const [leadData, setLeadData] = useState(null);

  return (
    <div className="min-h-screen bg-white">
      <LandingNavbar />

      {/* HERO */}
      <section className="bg-slate-50 border-b border-slate-200 py-14">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-2xl">
            <h1 className="text-4xl font-bold text-slate-900 mb-4">Talk to Our Sales Team</h1>
            <p className="text-lg text-slate-600 leading-relaxed mb-6">
              Enterprise and Elite plans are tailored to your practice network. Let's find the right fit.
            </p>
            <div className="flex flex-col sm:flex-row gap-5">
              <div className="flex items-center gap-2 text-slate-600">
                <Clock className="w-4 h-4 text-teal-500 shrink-0" />
                <span className="text-sm">Response within 24 hours</span>
              </div>
              <div className="flex items-center gap-2 text-slate-600">
                <ShieldCheck className="w-4 h-4 text-teal-500 shrink-0" />
                <span className="text-sm">HIPAA &amp; PIPEDA Ready</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FORM + CHAT */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-14 items-start">
            <SalesLeadForm
              requestedPlan={requestedPlan}
              onSuccess={setLeadData}
            />
            <CrispChatPanel
              name={leadData?.name ?? ''}
              email={leadData?.email ?? ''}
              clinicSize={leadData?.clinic_size ?? ''}
              requestedPlan={requestedPlan}
            />
          </div>
        </div>
      </section>

      <LandingFooter />
    </div>
  );
}
