import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import SalesLeadForm from './SalesLeadForm';
import CrispChatPanel from './CrispChatPanel';

const IS_DEV = process.env.REACT_APP_ENV === 'development';

export default function ContactSalesModal({ isOpen, onClose, requestedPlan }) {
  const navigate = useNavigate();
  const [leadData, setLeadData] = useState(null);
  const [chatOpen, setChatOpen] = useState(false);

  if (!isOpen) return null;

  const handleDevBypass = () => {
    onClose();
    navigate('/signup?plan=professional');
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Talk to Our Sales Team</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              {requestedPlan === 'elite' ? 'Elite' : 'Enterprise'} plan — response within 24 hours
            </p>
          </div>
          <button onClick={onClose} aria-label="Close"
            className="p-2 text-slate-400 hover:text-slate-600 transition-colors rounded-md hover:bg-slate-100">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

            {/* Left — form */}
            <div>
              <SalesLeadForm requestedPlan={requestedPlan} onSuccess={setLeadData} />

              {/* Dev-only bypass — excluded from production bundle by build-time constant */}
              {IS_DEV && (
                <div className="mt-6 pt-6 border-t border-dashed border-slate-300">
                  <p className="text-xs text-slate-400 mb-2">Dev only — not present in production build</p>
                  <button type="button" onClick={handleDevBypass}
                    className="w-full border border-slate-300 text-slate-600 hover:bg-slate-50 text-sm font-medium py-2.5 rounded-md transition-colors">
                    Continue to Signup (Dev Only)
                  </button>
                </div>
              )}
            </div>

            {/* Right — Crisp chat */}
            <div className="flex flex-col">
              {/* Mobile toggle — hidden on lg+ where both panes show */}
              <button type="button" onClick={() => setChatOpen(o => !o)}
                className="lg:hidden flex items-center gap-2 text-sm font-medium text-teal-600 mb-4">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                {chatOpen ? 'Hide live chat' : 'Open live chat'}
              </button>

              <div className={`flex-1 ${chatOpen ? 'block' : 'hidden'} lg:block`}>
                <CrispChatPanel
                  name={leadData?.name ?? ''}
                  email={leadData?.email ?? ''}
                  clinicSize={leadData?.clinic_size ?? ''}
                  requestedPlan={requestedPlan}
                />
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
