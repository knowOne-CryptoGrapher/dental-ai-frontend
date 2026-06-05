import React from 'react';

export default function TestimonialCard({ quote, name, title, clinic }) {
  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200 border-l-4 border-l-teal-500">
      <p className="text-slate-700 text-sm leading-relaxed mb-5">"{quote}"</p>
      <div>
        <p className="text-sm font-semibold text-slate-900">{name}</p>
        <p className="text-xs text-slate-500 mt-0.5">{title} · {clinic}</p>
      </div>
    </div>
  );
}
