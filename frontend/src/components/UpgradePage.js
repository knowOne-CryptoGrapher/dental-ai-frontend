import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, ArrowRight } from 'lucide-react';
import { Button } from './ui/button';

export default function UpgradePage({ feature, requiredTier }) {
  const navigate = useNavigate();
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="text-center max-w-sm px-4">
        <div className="flex items-center justify-center w-14 h-14 rounded-full bg-teal-50 mx-auto mb-4">
          <Sparkles className="w-7 h-7 text-teal-600" aria-hidden="true" />
        </div>
        <h2 className="text-xl font-bold text-gray-900 mb-2">Unlock {feature}</h2>
        <p className="text-sm text-gray-500 mb-6">
          <strong className="text-gray-900">{feature}</strong> is available on the{' '}
          <span className="font-semibold text-teal-700">{requiredTier}</span> plan and above.
          Upgrade your subscription to access this feature.
        </p>
        <Button
          className="bg-teal-600 hover:bg-teal-700 gap-1.5"
          onClick={() => navigate('/billing')}
        >
          Upgrade Plan
          <ArrowRight className="w-4 h-4" aria-hidden="true" />
        </Button>
      </div>
    </div>
  );
}
