import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Check, ArrowRight, Sparkles } from 'lucide-react';
import { Button } from './ui/button';

export default function FeatureUpgradeCard({
  featureName,
  description,
  bullets,
  requiredTier,
  ctaLabel,
}) {
  const navigate = useNavigate();
  const isElite = requiredTier === 'Elite';

  const iconBg    = isElite ? 'bg-yellow-50'                          : 'bg-teal-50';
  const iconColor = isElite ? 'text-[#b8962f]'                        : 'text-teal-600';
  const badgeCls  = isElite ? 'bg-yellow-50 border-yellow-200 text-yellow-800'
                             : 'bg-teal-50 border-teal-200 text-teal-700';
  const checkCls  = isElite ? 'text-[#b8962f]'                        : 'text-teal-500';
  const btnCls    = isElite ? 'bg-[#D4AF37] hover:bg-[#b8962f] text-white'
                             : 'bg-teal-600 hover:bg-teal-700';
  const cardBorder = isElite ? 'border-yellow-100'                    : 'border-gray-200';

  return (
    <div className="flex items-center justify-center min-h-[60vh] px-4">
      <div className="w-full max-w-md">

        <div className={`w-14 h-14 rounded-full ${iconBg} flex items-center justify-center mx-auto mb-5`}>
          <Sparkles className={`w-7 h-7 ${iconColor}`} aria-hidden="true" />
        </div>

        <div className="text-center mb-5">
          <h2 className="text-xl font-bold text-gray-900 mb-2">Unlock {featureName}</h2>
          <span className={`inline-flex items-center px-2.5 py-1 rounded-full border text-xs font-semibold ${badgeCls}`}>
            {requiredTier} plan and above
          </span>
        </div>

        <div className={`rounded-xl border ${cardBorder} bg-white p-5 mb-5 shadow-sm`}>
          <p className="text-sm text-gray-600 mb-4 leading-relaxed">{description}</p>
          <ul className="space-y-2.5">
            {bullets.map(bullet => (
              <li key={bullet} className="flex items-center gap-2.5 text-sm text-gray-700">
                <Check className={`w-4 h-4 shrink-0 ${checkCls}`} aria-hidden="true" />
                {bullet}
              </li>
            ))}
          </ul>
        </div>

        <div className="flex justify-center">
          <Button
            className={`gap-1.5 ${btnCls}`}
            onClick={() => navigate('/billing')}
          >
            {ctaLabel}
            <ArrowRight className="w-4 h-4" aria-hidden="true" />
          </Button>
        </div>

      </div>
    </div>
  );
}
