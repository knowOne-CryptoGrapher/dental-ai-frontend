import React, { useState } from 'react';
import { API_BASE_URL } from '../../config/api';

const CLINIC_SIZE_OPTIONS = ['1-5', '6-15', '16-50', '50+'];

export default function SalesLeadForm({ requestedPlan, onSuccess }) {
  const [form, setForm] = useState({
    name: '', email: '', phone: '', clinic_size: '', message: '',
  });
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const set = (key, val) => {
    setForm(f => ({ ...f, [key]: val }));
    setErrors(e => ({ ...e, [key]: undefined }));
  };

  const validate = () => {
    const e = {};
    if (!form.name.trim()) e.name = 'Required';
    if (!form.email.trim()) e.email = 'Required';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) e.email = 'Enter a valid email';
    if (!form.clinic_size) e.clinic_size = 'Required';
    return e;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }

    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/sales/contact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name:           form.name.trim(),
          email:          form.email.trim(),
          phone:          form.phone.trim() || null,
          clinic_size:    form.clinic_size,
          message:        form.message.trim() || null,
          requested_plan: requestedPlan,
        }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      setSubmitted(true);
      onSuccess?.({ ...form, requested_plan: requestedPlan, lead_id: data.lead_id });
    } catch {
      setErrors({ _form: 'Something went wrong. Please try again.' });
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="bg-teal-50 border border-teal-200 rounded-2xl p-10 text-center">
        <div className="w-14 h-14 bg-teal-100 rounded-full flex items-center justify-center mx-auto mb-5">
          <svg className="w-7 h-7 text-teal-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-slate-900 mb-3">We'll be in touch within 24 hours</h2>
        <p className="text-slate-600 leading-relaxed">A member of our sales team will reach out shortly.</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-5">
      {errors._form && (
        <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
          {errors._form}
        </p>
      )}

      <Field label="Name" required error={errors.name}>
        <input type="text" value={form.name} onChange={e => set('name', e.target.value)}
          placeholder="Jane Smith" className={inputCls(errors.name)} />
      </Field>

      <Field label="Email" required error={errors.email}>
        <input type="email" value={form.email} onChange={e => set('email', e.target.value)}
          placeholder="jane@mapleclinic.ca" className={inputCls(errors.email)} />
      </Field>

      <Field label="Phone Number" error={null}>
        <input type="tel" value={form.phone} onChange={e => set('phone', e.target.value)}
          placeholder="+1 (604) 555-0100" className={inputCls(null)} />
      </Field>

      <Field label="Clinic Size" required error={errors.clinic_size}>
        <select value={form.clinic_size} onChange={e => set('clinic_size', e.target.value)}
          className={selectCls}>
          <option value="">Select locations…</option>
          {CLINIC_SIZE_OPTIONS.map(o => <option key={o} value={o}>{o} locations</option>)}
        </select>
      </Field>

      <Field label="Message / Questions" error={null}>
        <textarea value={form.message} onChange={e => set('message', e.target.value)}
          placeholder="Tell us about your practice and what you're looking for."
          rows={4}
          className="w-full rounded-md border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500 transition resize-none" />
      </Field>

      <button type="submit" disabled={submitting}
        className="w-full bg-teal-600 hover:bg-teal-700 disabled:opacity-60 text-white font-semibold py-3 rounded-md transition-colors text-sm">
        {submitting ? 'Sending…' : 'Send Message'}
      </button>
    </form>
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
