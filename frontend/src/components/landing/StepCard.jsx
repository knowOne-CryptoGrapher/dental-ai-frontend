import React from 'react';

export default function StepCard({ number, title, description }) {
  return (
    <div className="flex flex-col items-center text-center px-4 relative z-10">
      <div className="w-14 h-14 rounded-full bg-teal-50 border-2 border-teal-200 flex items-center justify-center mb-5">
        <span className="text-teal-600 font-bold text-sm tracking-wide">{number}</span>
      </div>
      <h3 className="text-base font-semibold text-slate-900 mb-2">{title}</h3>
      <p className="text-sm text-slate-600 leading-relaxed">{description}</p>
    </div>
  );
}
