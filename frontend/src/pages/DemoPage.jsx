import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Clock, Users, Check } from 'lucide-react';
import LandingNavbar from '../components/landing/LandingNavbar';
import LandingFooter from '../components/landing/LandingFooter';

const LOCATION_OPTIONS = ['1', '2–5', '6–10', '10+'];
const SOURCE_OPTIONS = ['Google', 'Referral', 'Social Media', 'Dental Conference', 'Other'];

const WHAT_TO_EXPECT = [
  'A live walkthrough of the AI receptionist in action',
  'Custom configuration for your practice size and specialty',
  'Insurance verification and CDAnet integration demo',
  'Pricing and onboarding timeline for your specific needs',
];

export default function DemoPage() {
  const [form, setForm] = useState({
    firstName: '', lastName: '', email: '',
    phone: '', practiceName: '', locations: '', source: '',
  });
  const [errors, setErrors] = useState({});
  const [submitted, setSubmitted] = useState(false);

  const set = (key, val) => {
    setForm(f => ({ ...f, [key]: val }));
    setErrors(e => ({ ...e, [key]: undefined }));
  };

  const validate = () => {
    const e = {};
    if (!form.firstName.trim()) e.firstName = 'Required';
    if (!form.lastName.trim()) e.lastName = 'Required';
    if (!form.email.trim()) e.email = 'Required';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) e.email = 'Enter a valid email address';
    if (!form.practiceName.trim()) e.practiceName = 'Required';
    return e;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }
    setSubmitted(true);
  };

  return (
    <div className="min-h-screen bg-white">
      <LandingNavbar />

      {/* HERO */}
      <section className="bg-slate-50 border-b border-slate-200 py-14">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-2xl">
            <h1 className="text-4xl font-bold text-slate-900 mb-4">See Dental AI in Action</h1>
            <p className="text-lg text-slate-600 leading-relaxed mb-6">
              Book a personalized 30-minute demo with our team. We'll show you exactly how Dental AI
              works for your practice.
            </p>
            <div className="flex flex-col sm:flex-row gap-5">
              <div className="flex items-center gap-2 text-slate-600">
                <Clock className="w-4 h-4 text-teal-500 shrink-0" />
                <span className="text-sm">30-minute session</span>
              </div>
              <div className="flex items-center gap-2 text-slate-600">
                <Users className="w-4 h-4 text-teal-500 shrink-0" />
                <span className="text-sm">Personalized to your practice size</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* FORM + SIDEBAR */}
      <section className="py-16">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-14 items-start">

            {/* LEFT — form or confirmation */}
            <div>
              {submitted ? (
                <div className="bg-teal-50 border border-teal-200 rounded-2xl p-10 text-center">
                  <div className="w-14 h-14 bg-teal-100 rounded-full flex items-center justify-center mx-auto mb-5">
                    <Check className="w-7 h-7 text-teal-600" />
                  </div>
                  <h2 className="text-2xl font-bold text-slate-900 mb-3">
                    We'll be in touch within 24 hours
                  </h2>
                  <p className="text-slate-600 leading-relaxed mb-7">
                    A member of our team will reach out to confirm your demo time. In the meantime,
                    explore our pricing.
                  </p>
                  <Link
                    to="/pricing"
                    className="inline-block bg-teal-600 hover:bg-teal-700 text-white font-semibold px-6 py-2.5 rounded-md transition-colors text-sm"
                  >
                    View Pricing
                  </Link>
                </div>
              ) : (
                <form onSubmit={handleSubmit} noValidate className="space-y-5">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                    <Field label="First Name" required error={errors.firstName}>
                      <input
                        type="text"
                        value={form.firstName}
                        onChange={e => set('firstName', e.target.value)}
                        placeholder="Jane"
                        className={inputCls(errors.firstName)}
                      />
                    </Field>
                    <Field label="Last Name" required error={errors.lastName}>
                      <input
                        type="text"
                        value={form.lastName}
                        onChange={e => set('lastName', e.target.value)}
                        placeholder="Smith"
                        className={inputCls(errors.lastName)}
                      />
                    </Field>
                  </div>

                  <Field label="Email" required error={errors.email}>
                    <input
                      type="email"
                      value={form.email}
                      onChange={e => set('email', e.target.value)}
                      placeholder="jane@mapleclinic.ca"
                      className={inputCls(errors.email)}
                    />
                  </Field>

                  <Field label="Phone Number" error={null}>
                    <input
                      type="tel"
                      value={form.phone}
                      onChange={e => set('phone', e.target.value)}
                      placeholder="+1 (604) 555-0100"
                      className={inputCls(null)}
                    />
                  </Field>

                  <Field label="Practice Name" required error={errors.practiceName}>
                    <input
                      type="text"
                      value={form.practiceName}
                      onChange={e => set('practiceName', e.target.value)}
                      placeholder="Maple Dental Clinic"
                      className={inputCls(errors.practiceName)}
                    />
                  </Field>

                  <Field label="Number of Locations" error={null}>
                    <select
                      value={form.locations}
                      onChange={e => set('locations', e.target.value)}
                      className={selectCls}
                    >
                      <option value="">Select...</option>
                      {LOCATION_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  </Field>

                  <Field label="How did you hear about us?" error={null}>
                    <select
                      value={form.source}
                      onChange={e => set('source', e.target.value)}
                      className={selectCls}
                    >
                      <option value="">Select...</option>
                      {SOURCE_OPTIONS.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  </Field>

                  <button
                    type="submit"
                    className="w-full bg-teal-600 hover:bg-teal-700 text-white font-semibold py-3 rounded-md transition-colors text-sm"
                  >
                    Book My Demo
                  </button>
                </form>
              )}
            </div>

            {/* RIGHT — what to expect + pull quote */}
            <div className="space-y-6">
              <div className="bg-slate-50 rounded-2xl border border-slate-200 p-7">
                <h2 className="text-lg font-bold text-slate-900 mb-5">What to expect</h2>
                <ul className="space-y-3.5">
                  {WHAT_TO_EXPECT.map(item => (
                    <li key={item} className="flex items-start gap-3">
                      <Check className="w-4 h-4 text-teal-500 mt-0.5 shrink-0" />
                      <span className="text-sm text-slate-700 leading-relaxed">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <blockquote className="border-l-4 border-teal-500 pl-5 py-1">
                <p className="text-sm text-slate-700 leading-relaxed italic mb-3">
                  "The demo sold us in 20 minutes. We were live within the week."
                </p>
                <footer>
                  <span className="text-xs font-semibold text-slate-900">Dr. Sarah Mitchell</span>
                  <span className="text-xs text-slate-500"> · Mitchell Family Dental</span>
                </footer>
              </blockquote>
            </div>

          </div>
        </div>
      </section>

      <LandingFooter />
    </div>
  );
}

function Field({ label, required, error, children }) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1.5">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
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
