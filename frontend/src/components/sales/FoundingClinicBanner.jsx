import React, { useState } from 'react';
import { X } from 'lucide-react';
import FoundingClinicModal from './FoundingClinicModal';

const DISMISS_KEY = 'founding_banner_dismissed';

export default function FoundingClinicBanner() {
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(DISMISS_KEY) === 'true');
  const [modalOpen, setModalOpen] = useState(false);

  const handleDismiss = () => {
    localStorage.setItem(DISMISS_KEY, 'true');
    setDismissed(true);
  };

  if (dismissed) return null;

  return (
    <>
      <div className="bg-teal-700 text-white relative">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5 pr-10 flex items-center justify-center gap-3 flex-wrap text-sm">
          <span className="font-medium text-center">
            🦷 Founding Clinic Program — 10 spots, 40% off for life. BC clinics only.
          </span>
          <button
            onClick={() => setModalOpen(true)}
            className="font-semibold underline underline-offset-2 hover:no-underline whitespace-nowrap"
          >
            Learn More →
          </button>
        </div>
        <button
          onClick={handleDismiss}
          aria-label="Dismiss banner"
          className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 text-teal-100 hover:text-white hover:bg-teal-600 rounded transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <FoundingClinicModal isOpen={modalOpen} onClose={() => setModalOpen(false)} />
    </>
  );
}
