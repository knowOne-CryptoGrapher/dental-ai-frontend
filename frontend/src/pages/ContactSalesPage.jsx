import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Clock, ShieldCheck, Check } from 'lucide-react';
import LandingNavbar from '../components/landing/LandingNavbar';
import LandingFooter from '../components/landing/LandingFooter';

const LOCATION_OPTIONS = ['1', '2–5', '6–10', '10+'];

const PLAN_BULLETS = {
  Enterprise: [
    'Up to 25 locations and 50 providers',
    'Knowledge Base and Custom Routing Rules',
    '2,500 AI calls per month',
    'Custom voice configuration',
  ],
  Elite: [
    'Up to 100 locations and 200 providers',
    'Signed HIPAA/PIPEDA BAA included',
    'Dedicated Support SLA — 4hr response',
    'Custom AI model selection',
  ],
};

function planFromParam(param) {
  if (param === 'elite') return 'Elite';
  return 'Enterprise';
}

export default function ContactSalesPage() {
  const [searchParams] = useSearchParams();
  const initialPlan = planFromParam(searchParams.get('plan'));

  const [form, setForm] = useState({
    firstName: '', lastName: '', email: '',
    phone: '', practiceName: '', locations: '',
    plan: initialPlan, message: '',
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

    const subject = encodeURIComponent(
      `Dental AI ${form.plan} Inquiry — ${form.practiceName.trim()}`
    );
    const body = encodeURIComponent(
      `Name: ${form.firstName.trim()} ${form.lastName.trim()}\n` +
      `Email: ${form.email.trim()}\n` +
      `Phone: ${form.phone.trim() || 'Not provided'}\n` +
      `Practice: ${form.practiceName.trim()}\n` +
      `Locations: ${form.locations || 'Not specified'}\n` +
      `Plan Interest: ${form.plan}\n` +
      `Message: ${form.message.trim() || 'None'}\n`
    );
    window.location.href = `mailto:sales@placeholder.com?subject=${subject}&body=${body}`;
    setSubmitted(true);
  };

  const isElite = form.plan === 'Elite';
  const bullets = PLAN_BULLETS[form.plan] ?? PLAN_BULLETS.Enterprise;

  return (
    <div className="min-h-screen bg-white">
      <LandingNavbar />

      {/* HERO */}
      <section className="bg-slate-50 border-b border-slate-200 py-14">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="max-w-2xl">
            <h1 className="text-4xl font-bold text-slate-900 mb-4">Talk to Our Sales Team</h1>
            <p className="text-lg text-slate-600 leading-relaxed mb-6">
              Enterprise and Elite plans are tailored to your practice network. Let's find the right fit.
            </p>
            <div className="flex flex-col sm:flex-row gap-5">
              <div className="flex items-center gap-2 text-slate-600">
                <Clock className="w-4 h-4 text-teal-500 shrink-0" />
                <span className="text-sm">Response within 24 hours</span>
              </div>
              <div className="flex items-center gap-2 text-slate-600">
                <ShieldCheck className="w-4 h-4 text-teal-500 shrink-0" />
                <span className="text-sm">HIPAA &amp; PIPEDA Ready</span>
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
                    A member of our sales team will reach out shortly. In the meantime, you can review
                    our full pricing comparison.
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

                  <Field label="Plan Interest" error={null}>
                    <select
                      value={form.plan}
                      onChange={e => set('plan', e.target.value)}
                      className={selectCls}
                    >
                      <option value="Enterprise">Enterprise</option>
                      <option value="Elite">Elite</option>
                    </select>
                  </Field>

                  <Field label="Message / Questions" error={null}>
                    <textarea
                      value={form.message}
                      onChange={e => set('message', e.target.value)}
                      placeholder="Tell us about your practice and what you're looking for."
                      rows={4}
                      className="w-full rounded-md border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500 transition resize-none"
                    />
                  </Field>

                  <button
                    type="submit"
                    className="w-full bg-teal-600 hover:bg-teal-700 text-white font-semibold py-3 rounded-md transition-colors text-sm"
                  >
                    Send Message
                  </button>
                </form>
              )}
            </div>

            {/* RIGHT — value card + compliance note */}
            <div className="space-y-6">
              <div
                className="rounded-2xl p-7"
                style={isElite
                  ? { border: '2px solid #D4AF37', background: '#fffdf5' }
                  : { border: '1px solid rgb(226 232 240)', background: 'rgb(248 250 252)' }}
              >
                <h2 className="text-lg font-bold text-slate-900 mb-5">Built for growing practices</h2>
                <ul className="space-y-3.5">
                  {bullets.map(item => (
                    <li key={item} className="flex items-start gap-3">
                      <Check
                        className="w-4 h-4 mt-0.5 shrink-0"
                        style={{ color: isElite ? '#D4AF37' : '#14b8a6' }}
                      />
                      <span className="text-sm text-slate-700 leading-relaxed">{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="flex items-start gap-3 bg-slate-50 rounded-xl border border-slate-200 px-5 py-4">
                <ShieldCheck className="w-5 h-5 text-teal-500 shrink-0 mt-0.5" />
                <p className="text-sm text-slate-600 leading-relaxed">
                  All plans include PHI-safe infrastructure, Canadian data residency, and SOC 2 security controls.
                </p>
              </div>
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
