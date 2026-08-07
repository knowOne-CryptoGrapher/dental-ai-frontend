import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../../config/api';
import { Check, X, ArrowRight, Loader2 } from 'lucide-react';

const PROVINCES = [
  { code: 'BC',    label: 'British Columbia', enabled: true },
  { code: 'AB',    label: 'Alberta',          enabled: false },
  { code: 'ON',    label: 'Ontario',          enabled: false },
  { code: 'QC',    label: 'Quebec',           enabled: false },
  { code: 'OTHER', label: 'Other',            enabled: false },
];

const INITIAL_FORM = { name: '', clinic_name: '', email: '', phone: '', province: 'BC' };

export default function FoundingClinicModal({ isOpen, onClose }) {
  const [form, setForm] = useState(INITIAL_FORM);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [spotsRemaining, setSpotsRemaining] = useState(null);
  const [countLoading, setCountLoading] = useState(true);

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    setCountLoading(true);
    fetch(`${API_BASE_URL}/api/sales/founding-clinic-count`)
      .then(res => res.json())
      .then(data => { if (!cancelled) setSpotsRemaining(data.spots_remaining); })
      .catch(() => { if (!cancelled) setSpotsRemaining(null); })
      .finally(() => { if (!cancelled) setCountLoading(false); });
    return () => { cancelled = true; };
  }, [isOpen]);

  if (!isOpen) return null;

  const set = (key) => (e) => {
    setForm(f => ({ ...f, [key]: e.target.value }));
    setErrors(er => ({ ...er, [key]: undefined }));
  };

  const validate = () => {
    const e = {};
    if (!form.name.trim()) e.name = 'Required';
    if (!form.clinic_name.trim()) e.clinic_name = 'Required';
    if (!form.email.trim()) e.email = 'Required';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) e.email = 'Enter a valid email';
    if (!form.phone.trim()) e.phone = 'Required';
    return e;
  };

  const handleSubmit = async (ev) => {
    ev.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }

    setSubmitting(true);
    setErrors({});
    try {
      const res = await fetch(`${API_BASE_URL}/api/sales/founding-clinic`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || `${res.status}`);
      }
      setSubmitted(true);
    } catch (err) {
      setErrors({ _form: typeof err.message === 'string' && !/^\d+$/.test(err.message) ? err.message : 'Something went wrong. Please try again.' });
    } finally {
      setSubmitting(false);
    }
  };

  const isFull = spotsRemaining === 0;
  const isUrgent = spotsRemaining !== null && spotsRemaining > 0 && spotsRemaining <= 3;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
          <div>
            <h2 className="text-lg font-bold text-slate-900">🦷 Founding Clinic Program</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              Limited to 10 clinics{spotsRemaining !== null && ` — ${spotsRemaining} spot${spotsRemaining === 1 ? '' : 's'} remaining`}
            </p>
          </div>
          <button onClick={onClose} aria-label="Close"
            className="p-2 text-slate-400 hover:text-slate-600 transition-colors rounded-md hover:bg-slate-100">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {submitted ? (
            <div className="text-center py-6">
              <div className="w-14 h-14 bg-teal-100 rounded-full flex items-center justify-center mx-auto mb-5">
                <Check className="w-7 h-7 text-teal-600" />
              </div>
              <h3 className="text-xl font-bold text-slate-900 mb-3">
                {isFull ? "You're on the waitlist" : "You're in!"}
              </h3>
              <p className="text-slate-600 leading-relaxed">We'll be in touch within 24 hours to get you set up.</p>
            </div>
          ) : (
            <>
              {/* Offer card */}
              <div className="bg-teal-50 border border-teal-200 rounded-xl p-5 text-center">
                <div className="flex items-baseline justify-center gap-2">
                  <span className="text-4xl font-bold text-teal-700">$299</span>
                  <span className="text-sm text-slate-500">/mo</span>
                </div>
                <p className="text-sm text-slate-400 line-through mt-1">Regular price $499/mo</p>
                <p className="text-xs font-semibold text-teal-700 mt-2">Locked for life — never increases</p>
              </div>

              {/* Spots counter */}
              {!countLoading && spotsRemaining !== null && (
                <div className={`text-center text-sm font-semibold px-3 py-2 rounded-lg border ${
                  isFull
                    ? 'bg-red-50 text-red-700 border-red-200'
                    : isUrgent
                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                    : 'bg-slate-50 text-slate-600 border-slate-200'
                }`}>
                  {isFull ? 'All 10 spots are taken' : `${spotsRemaining} of 10 spots remaining`}
                </div>
              )}

              <p className="text-slate-700 text-sm leading-relaxed">
                Be one of our 10 Founding Clinics and lock in 40% off forever.
              </p>

              <div>
                <p className="text-sm font-semibold text-slate-900 mb-2">What you get:</p>
                <ul className="space-y-1.5">
                  {[
                    'Full AI receptionist — answers every call, books appointments 24/7',
                    'Patient lookup and appointment management',
                    'Real-time call logs and dashboard',
                    'Dedicated onboarding support',
                    'Founding Clinic rate locked for life',
                  ].map(item => (
                    <li key={item} className="flex items-start gap-2 text-sm text-slate-600">
                      <Check className="w-4 h-4 text-teal-500 shrink-0 mt-0.5" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <p className="text-sm font-semibold text-slate-900 mb-2">What we ask:</p>
                <ul className="space-y-1.5">
                  {[
                    'Weekly feedback for the first 60 days',
                    'A testimonial if you love it',
                  ].map(item => (
                    <li key={item} className="flex items-start gap-2 text-sm text-slate-600">
                      <ArrowRight className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>

              <p className="text-xs text-slate-400 italic">Currently available to BC clinics only.</p>

              {isFull && (
                <p className="text-sm text-slate-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
                  All spots are taken — join the waitlist and we'll notify you when we expand.
                </p>
              )}

              {/* Form */}
              <form onSubmit={handleSubmit} noValidate className="space-y-4 pt-2 border-t border-slate-100">
                {errors._form && (
                  <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
                    {errors._form}
                  </p>
                )}

                <Field label="Your Name" required error={errors.name}>
                  <input type="text" value={form.name} onChange={set('name')}
                    placeholder="Jane Smith" className={inputCls(errors.name)} />
                </Field>

                <Field label="Clinic Name" required error={errors.clinic_name}>
                  <input type="text" value={form.clinic_name} onChange={set('clinic_name')}
                    placeholder="Maple Dental Clinic" className={inputCls(errors.clinic_name)} />
                </Field>

                <Field label="Email" required error={errors.email}>
                  <input type="email" value={form.email} onChange={set('email')}
                    placeholder="jane@mapleclinic.ca" className={inputCls(errors.email)} />
                </Field>

                <Field label="Phone" required error={errors.phone}>
                  <input type="tel" value={form.phone} onChange={set('phone')}
                    placeholder="+1 (604) 555-0100" className={inputCls(errors.phone)} />
                </Field>

                <Field label="Province" required error={null}>
                  <select value={form.province} onChange={set('province')} className={selectCls}>
                    {PROVINCES.map(p => (
                      <option key={p.code} value={p.code} disabled={!p.enabled}>
                        {p.label}{!p.enabled ? ' (Coming soon)' : ''}
                      </option>
                    ))}
                  </select>
                </Field>

                <button type="submit" disabled={submitting}
                  className="w-full bg-teal-600 hover:bg-teal-700 disabled:opacity-60 text-white font-semibold py-3 rounded-md transition-colors text-sm flex items-center justify-center gap-1.5">
                  {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
                  {isFull ? 'Join the Waitlist' : 'Claim Your Spot'} <ArrowRight className="w-4 h-4" />
                </button>

                <p className="text-xs text-slate-400 text-center">
                  We'll be in touch within 24 hours to get you set up.
                </p>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, required, error, children }) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1.5">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  );
}

const inputCls = (error) =>
  `w-full h-10 rounded-md border px-3 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500 transition ${
    error ? 'border-red-400' : 'border-slate-300'
  }`;

const selectCls =
  'w-full h-10 rounded-md border border-slate-300 px-3 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-teal-500 bg-white transition';
