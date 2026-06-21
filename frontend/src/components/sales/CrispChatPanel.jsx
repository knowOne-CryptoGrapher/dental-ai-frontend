import React, { useEffect } from 'react';

const CRISP_WEBSITE_ID = process.env.REACT_APP_CRISP_WEBSITE_ID || '';

function initCrisp() {
  if (window.$crisp) return;
  window.$crisp = [];
  window.CRISP_WEBSITE_ID = CRISP_WEBSITE_ID;
  const s = document.createElement('script');
  s.src = 'https://client.crisp.chat/l.js';
  s.async = true;
  document.head.appendChild(s);
}

export default function CrispChatPanel({ name, email, clinicSize, requestedPlan }) {
  useEffect(() => {
    if (!CRISP_WEBSITE_ID) return;
    initCrisp();
    // $crisp queues commands before load, executes them on ready — safe to push immediately
    if (email) window.$crisp.push(['set', 'user:email', [email]]);
    if (name)  window.$crisp.push(['set', 'user:nickname', [name]]);
    window.$crisp.push(['set', 'session:data', [[
      ['clinic_size', clinicSize || ''],
      ['requested_plan', requestedPlan || ''],
    ]]]);
    window.$crisp.push(['do', 'chat:open']);
  }, [name, email, clinicSize, requestedPlan]);

  if (!CRISP_WEBSITE_ID) {
    return (
      <div className="h-full min-h-[400px] flex items-center justify-center bg-slate-50 rounded-xl border border-slate-200">
        <p className="text-sm text-slate-400 text-center px-6">
          Live chat not configured.{' '}
          Set <code className="text-xs bg-slate-100 px-1 py-0.5 rounded">REACT_APP_CRISP_WEBSITE_ID</code> to enable.
        </p>
      </div>
    );
  }

  return (
    <div className="h-full min-h-[400px] bg-slate-50 rounded-xl border border-slate-200 flex items-center justify-center">
      <p className="text-sm text-slate-500">Loading chat…</p>
    </div>
  );
}
