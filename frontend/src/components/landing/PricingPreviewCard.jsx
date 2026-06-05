import React from 'react';
import { Link } from 'react-router-dom';
import { Check } from 'lucide-react';

export default function PricingPreviewCard({ name, price, badge, features, ctaLabel, ctaHref, isElite, isPopular }) {
  const isMailto = ctaHref?.startsWith('mailto:');

  const cardClass = [
    'bg-white rounded-xl p-6 flex flex-col shadow-sm relative',
    isElite ? '' : isPopular ? 'border-2 border-teal-600' : 'border border-slate-200',
  ].join(' ');

  const cardStyle = isElite ? { border: '2px solid #D4AF37' } : {};

  const ctaClass = [
    'block text-center py-2.5 px-4 rounded-md text-sm font-semibold transition-colors',
    isElite
      ? 'text-white hover:opacity-90'
      : isPopular
      ? 'bg-teal-600 hover:bg-teal-700 text-white'
      : 'border border-teal-600 text-teal-600 hover:bg-teal-50',
  ].join(' ');

  const ctaStyle = isElite ? { backgroundColor: '#D4AF37' } : {};

  return (
    <div className={cardClass} style={cardStyle}>
      {badge && (
        <span
          className={`absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-[11px] font-semibold whitespace-nowrap ${isElite ? 'text-white' : 'bg-teal-600 text-white'}`}
          style={isElite ? { backgroundColor: '#D4AF37' } : {}}
        >
          {badge}
        </span>
      )}

      <div className="mb-5">
        <h3 className={`text-lg font-bold mb-1 ${isElite ? 'text-[#b8962f]' : 'text-slate-900'}`}>{name}</h3>
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-bold text-slate-900">{price}</span>
          <span className="text-sm text-slate-500">/mo</span>
        </div>
      </div>

      <ul className="space-y-2 flex-1 mb-6">
        {features.map((f, i) => (
          <li key={i} className="flex items-start gap-2">
            <Check className={`w-4 h-4 mt-0.5 shrink-0 ${isElite ? 'text-[#D4AF37]' : 'text-teal-500'}`} />
            <span className="text-sm text-slate-600">{f}</span>
          </li>
        ))}
      </ul>

      {isMailto ? (
        <a href={ctaHref} className={ctaClass} style={ctaStyle}>
          {ctaLabel}
        </a>
      ) : (
        <Link to={ctaHref} className={ctaClass} style={ctaStyle}>
          {ctaLabel}
        </Link>
      )}
    </div>
  );
}
