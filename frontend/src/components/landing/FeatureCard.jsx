import React from 'react';

export default function FeatureCard({ icon: Icon, title, description }) {
  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-slate-200/80 hover:shadow-md transition-shadow">
      <div className="w-11 h-11 rounded-lg bg-teal-50 flex items-center justify-center mb-4">
        <Icon className="w-5 h-5 text-teal-600" />
      </div>
      <h3 className="text-base font-semibold text-slate-900 mb-2">{title}</h3>
      <p className="text-sm text-slate-600 leading-relaxed">{description}</p>
    </div>
  );
}
