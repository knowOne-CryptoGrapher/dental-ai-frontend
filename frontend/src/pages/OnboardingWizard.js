import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Navigate } from 'react-router-dom';
import {
  Check,
  Copy,
  ChevronRight,
  ChevronLeft,
  Loader2,
  Phone,
  Clock,
  AlertTriangle,
  ClipboardList,
  Sparkles,
  User,
  CreditCard,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { toast } from 'sonner';

import { useAuth } from '@/hooks/useAuth';
import { api } from '@/config/api';
import { TERMS_VERSION, PRIVACY_POLICY_VERSION } from '@/config/legal';

const CANADIAN_PROVINCES = [
  { code: 'AB', label: 'Alberta' },
  { code: 'BC', label: 'British Columbia' },
  { code: 'MB', label: 'Manitoba' },
  { code: 'NB', label: 'New Brunswick' },
  { code: 'NL', label: 'Newfoundland and Labrador' },
  { code: 'NS', label: 'Nova Scotia' },
  { code: 'NT', label: 'Northwest Territories' },
  { code: 'NU', label: 'Nunavut' },
  { code: 'ON', label: 'Ontario' },
  { code: 'PE', label: 'Prince Edward Island' },
  { code: 'QC', label: 'Quebec' },
  { code: 'SK', label: 'Saskatchewan' },
  { code: 'YT', label: 'Yukon' },
];

const STEPS = [
  { id: 0,  name: 'Welcome',           icon: Sparkles      },
  { id: 1,  name: 'Account',           icon: User          },
  { id: 2,  name: 'Plan',              icon: CreditCard    },
  { id: 3,  name: 'Practice Basics',   icon: ClipboardList },
  { id: 4,  name: 'Hours',             icon: Clock         },
  { id: 5,  name: 'Providers',         icon: ClipboardList },
  { id: 6,  name: 'Appointment Types', icon: ClipboardList },
  { id: 7,  name: 'Branding',          icon: Sparkles      },
  { id: 8,  name: 'Emergency Rules',   icon: AlertTriangle },
  { id: 9,  name: 'Retell Setup',      icon: Phone         },
  { id: 10, name: 'Test & Finish',     icon: Check         },
];

// Plan data — mirrors plans.py
const WIZARD_PLANS = [
  {
    id: 'basic',
    name: 'Basic',
    price: '$399',
    badge: null,
    isElite: false,
    isPopular: false,
    limits: ['250 calls/mo', '5 providers', '1 location'],
  },
  {
    id: 'professional',
    name: 'Professional',
    price: '$599',
    badge: 'Most Popular',
    isElite: false,
    isPopular: true,
    limits: ['750 calls/mo', '15 providers', '5 locations'],
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: '$999',
    badge: null,
    isElite: false,
    isPopular: false,
    limits: ['2,500 calls/mo', '50 providers', '25 locations'],
  },
  {
    id: 'elite',
    name: 'Elite',
    price: '$1,499',
    badge: 'Most Powerful',
    isElite: true,
    isPopular: false,
    limits: ['10,000 calls/mo', '200 providers', '100 locations'],
  },
];

const CONTACT_SALES_PLANS = ['enterprise', 'elite'];
const requiresContactSales = (planId) => CONTACT_SALES_PLANS.includes(planId);

const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const DAY_LABELS = {
  mon: 'Mon',
  tue: 'Tue',
  wed: 'Wed',
  thu: 'Thu',
  fri: 'Fri',
  sat: 'Sat',
  sun: 'Sun',
};

function StepWrapper({ step, children }) {
  return (
    <Card className="max-w-3xl mx-auto mt-10 shadow-lg">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {React.createElement(STEPS[step].icon, { className: 'w-5 h-5 text-blue-600' })}
          {STEPS[step].name}
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function CopyButton({ text, label = 'Copy' }) {
  const [copied, setCopied] = useState(false);

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          toast.error('Copy failed');
        }
      }}
    >
      {copied ? <Check className="w-4 h-4 mr-1" /> : <Copy className="w-4 h-4 mr-1" />}
      {copied ? 'Copied!' : label}
    </Button>
  );
}

export default function OnboardingWizard({ mode = 'signup' }) {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    user,
    practice,
    loadToken,
    refreshPractice,
    isSuperAdmin,
  } = useAuth();

  const [step, setStep] = useState(
    mode === 'resume' && practice?.onboarding_step
      ? Math.min(practice.onboarding_step, STEPS.length - 1)
      : 0
  );
  const [saving, setSaving] = useState(false);

  // Whether the plan was pre-selected via ?plan= URL param — never changes
  const [planFromUrl] = useState(!!searchParams.get('plan'));
  // The committed plan sent to POST /practices
  const [selectedPlan, setSelectedPlan] = useState(searchParams.get('plan') || '');

  // Live self-serve availability per plan id, from the same SELF_SERVE_TIERS_ENABLED
  // source of truth as plans.py / PricingPage.jsx — null until loaded.
  const [selfServeTiers, setSelfServeTiers] = useState(null);

  const [signup, setSignup] = useState({
    practice_name: '',
    province: '',
    timezone: 'America/Toronto',
    admin_email: '',
    admin_password: '',
    admin_full_name: '',
    contact_phone: '',
  });
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [acceptedPrivacy, setAcceptedPrivacy] = useState(false);
  const [signupErrors, setSignupErrors] = useState({});

  const [hours, setHours] = useState({
    timezone: 'America/Toronto',
    weekly: {
      mon: { open: '08:00', close: '17:00' },
      tue: { open: '08:00', close: '17:00' },
      wed: { open: '08:00', close: '17:00' },
      thu: { open: '08:00', close: '17:00' },
      fri: { open: '08:00', close: '15:00' },
      sat: null,
      sun: null,
    },
    closed_dates: [],
  });

  const [providers, setProviders] = useState([]);
  const [newProvider, setNewProvider] = useState({ name: '', role: 'Dentist' });

  const [apptTypes, setApptTypes] = useState([]);
  const [newType, setNewType] = useState({ id: '', name: '', duration_min: 30 });

  const [branding, setBranding] = useState({
    agent_name: 'Amanda',
    greeting: '',
    closing: 'Thank you for calling. Have a great day!',
    voice_tone: 'warm_professional',
  });

  const [emergency, setEmergency] = useState({
    triggers: ['severe pain', 'swelling', 'bleeding', 'trauma'],
    response_policy: 'earliest_available',
    after_hours_handoff_phone: '',
  });

  const [retellPayload, setRetellPayload] = useState(null);
  const [retellAgentId, setRetellAgentId] = useState('');
  const [retellPhone, setRetellPhone] = useState('');

  useEffect(() => {
    if (practice?.settings) {
      setHours(practice.settings.hours || hours);
      setApptTypes(practice.settings.appointment_types || []);
      setBranding(practice.settings.branding || branding);
      setEmergency(practice.settings.emergency || emergency);
      setRetellAgentId(practice.settings.retell?.agent_id || '');
      setRetellPhone(practice.settings.retell?.phone_number || '');
    }
  }, [practice]);

  useEffect(() => {
    if (mode === 'resume' && practice?.onboarding_step != null) {
      setStep(Math.min(practice.onboarding_step, STEPS.length - 1));
    }
  }, [practice?.onboarding_step, mode]);

  useEffect(() => {
    let cancelled = false;
    api.get('/billing/plans')
      .then((res) => {
        if (cancelled) return;
        const map = {};
        res.data.forEach((p) => { map[p.id] = p.self_serve_enabled; });
        setSelfServeTiers(map);
      })
      .catch(() => { if (!cancelled) setSelfServeTiers({}); });
    return () => { cancelled = true; };
  }, []);

  // Catch a locked plan as early as possible — whether pre-selected via a
  // direct ?plan= URL or chosen from this wizard's own plan step — instead
  // of letting the whole form get filled out and hitting the 400 from
  // POST /practices at the very end. Deliberately NOT scoped to Professional
  // only (unlike the Step 2 grid's visual lock below) — SELF_SERVE_TIERS_ENABLED
  // blocks any non-basic plan server-side today, including enterprise/elite if
  // someone lands here via a direct ?plan=enterprise URL bypassing Contact
  // Sales entirely, so this safety net stays general to catch all of them.
  useEffect(() => {
    if (mode === 'resume') return;             // existing practices are never re-validated
    if (!selectedPlan) return;                  // nothing selected yet
    if (selfServeTiers === null) return;         // availability not loaded yet
    if (selfServeTiers[selectedPlan] !== true) {
      toast.error(
        `${selectedPlan.charAt(0).toUpperCase()}${selectedPlan.slice(1)} isn't open for self-serve signup yet. Contact sales to get started.`
      );
      navigate('/pricing');
    }
  }, [mode, selectedPlan, selfServeTiers, navigate]);

  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const back = () => setStep((s) => Math.max(s - 1, 0));

  // ── Step 1: Account creation (POST /auth/signup only) ─────────────────────
  const handleAccountCreation = async () => {
    const errors = {};
    if (!signup.admin_full_name.trim())
      errors.admin_full_name = 'Full name is required';
    if (!signup.admin_email.trim() || !signup.admin_email.includes('@'))
      errors.admin_email = 'A valid email address is required';
    if (!signup.admin_password || signup.admin_password.length < 8)
      errors.admin_password = 'Password must be at least 8 characters';

    if (Object.keys(errors).length > 0) {
      setSignupErrors(errors);
      return;
    }
    setSignupErrors({});

    setSaving(true);
    try {
      const signupRes = await api.post('/auth/signup', {
        email: signup.admin_email,
        password: signup.admin_password,
        full_name: signup.admin_full_name,
        contact_phone: signup.contact_phone,
      });
      loadToken(signupRes.data.access_token);

      if (selectedPlan) {
        setStep(3); // plan already set — skip plan selection
      } else {
        next(); // go to plan selection (step 2)
      }
    } catch (err) {
      console.error('Account creation failed:', err);
      const detail = err?.response?.data?.detail;

      if (Array.isArray(detail)) {
        const backendErrors = {};
        detail.forEach((e) => {
          const field = e.loc?.[e.loc.length - 1];
          if (field) backendErrors[field] = e.msg;
        });
        if (Object.keys(backendErrors).length > 0) {
          setSignupErrors(backendErrors);
          return;
        }
      }

      if (err?.response?.status === 409) {
        setSignupErrors({
          admin_email: detail || 'An account with this email already exists. Please log in instead.',
        });
        return;
      }

      if (typeof detail === 'string') {
        if (detail.toLowerCase().includes('email')) {
          setSignupErrors({ admin_email: detail });
          return;
        }
      }

      toast.error(typeof detail === 'string' ? detail : 'Account creation failed');
    } finally {
      setSaving(false);
    }
  };

  // ── Step 3: Practice creation (POST /practices only) ──────────────────────
  const handlePracticeCreation = async () => {
    const errors = {};
    if (!signup.practice_name.trim())
      errors.practice_name = 'Practice name is required';
    if (!signup.province)
      errors.province = 'Please select your province or territory';
    if (!acceptedTerms)
      errors.terms = 'You must accept the Terms & Conditions';
    if (!acceptedPrivacy)
      errors.privacy = 'You must accept the Privacy Policy';

    if (Object.keys(errors).length > 0) {
      setSignupErrors(errors);
      return;
    }
    setSignupErrors({});

    setSaving(true);
    try {
      const practiceRes = await api.post('/practices', {
        name: signup.practice_name,
        province: signup.province,
        timezone: signup.timezone || 'America/Toronto',
        contact_phone: signup.contact_phone,
        plan: selectedPlan,
        accepted_terms_version: TERMS_VERSION,
        accepted_privacy_version: PRIVACY_POLICY_VERSION,
        accepted_at: new Date().toISOString(),
      });
      loadToken(practiceRes.data.access_token);
      setSearchParams({}, { replace: true });
      toast.success('Practice created!');
      next();
    } catch (err) {
      console.error('Practice creation failed:', err);
      const detail = err?.response?.data?.detail;

      if (err?.response?.status === 400) {
        toast.error(typeof detail === 'string' ? detail : 'Invalid plan or request');
        return;
      }

      if (typeof detail === 'string' && detail.toLowerCase().includes('practice')) {
        setSignupErrors({ practice_name: detail });
        return;
      }

      toast.error(typeof detail === 'string' ? detail : 'Failed to create practice');
    } finally {
      setSaving(false);
    }
  };

  const saveHours = async () => {
    setSaving(true);
    try {
      await api.put(`/practice/${user?.practice_id}/hours`, hours);
      try {
        await api.patch(`/practices/${user?.practice_id}/onboarding-step`, { onboarding_step: step + 1 });
      } catch (patchErr) {
        console.error('Failed to update onboarding step:', patchErr);
      }
      toast.success('Hours saved');
      next();
    } catch (err) {
      console.error('Failed to save hours:', err);
      toast.error(err?.response?.data?.detail || 'Failed to save hours');
    } finally {
      setSaving(false);
    }
  };

  const addProvider = async () => {
    if (!newProvider.name) return;
    setSaving(true);
    try {
      const res = await api.post('/providers', newProvider);
      setProviders([...providers, res.data]);
      setNewProvider({ name: '', role: 'Dentist' });
      toast.success('Provider added');
    } catch (err) {
      console.error('Failed to add provider:', err);
      toast.error(err?.response?.data?.detail || 'Failed to add provider');
    } finally {
      setSaving(false);
    }
  };

  const removeProvider = async (id) => {
    setSaving(true);
    try {
      await api.delete(`/providers/${id}`);
      setProviders(providers.filter((p) => p.id !== id));
      toast.success('Provider removed');
    } catch (err) {
      console.error('Failed to remove provider:', err);
      toast.error(err?.response?.data?.detail || 'Failed to remove provider');
    } finally {
      setSaving(false);
    }
  };

  const addApptType = async () => {
    if (!newType.name) return;
    setSaving(true);
    try {
      const typeToSend = {
        ...newType,
        id: newType.name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '') + '-' + Date.now(),
      };
      const res = await api.post(`/practice/${user?.practice_id}/appointment-types`, typeToSend);
      setApptTypes(res.data);
      setNewType({ id: '', name: '', duration_min: 30 });
      toast.success('Appointment type added');
    } catch (err) {
      console.error('Failed to add appointment type:', err);
      toast.error(err?.response?.data?.detail || 'Failed to add appointment type');
    } finally {
      setSaving(false);
    }
  };

  const removeApptType = async (id) => {
    setSaving(true);
    try {
      await api.delete(`/practice/${user?.practice_id}/appointment-types/${id}`);
      setApptTypes(apptTypes.filter((t) => t.id !== id));
      toast.success('Appointment type removed');
    } catch (err) {
      console.error('Failed to remove appointment type:', err);
      toast.error(err?.response?.data?.detail || 'Failed to remove appointment type');
    } finally {
      setSaving(false);
    }
  };

  const handleProvidersContinue = async () => {
    try {
      await api.patch(
        `/practices/${user?.practice_id}/onboarding-step`,
        { onboarding_step: step + 1 }
      );
    } catch (err) {
      console.error('Failed to update onboarding step:', err);
    }
    next();
  };

  const handleApptTypesContinue = async () => {
    try {
      await api.patch(
        `/practices/${user?.practice_id}/onboarding-step`,
        { onboarding_step: step + 1 }
      );
    } catch (err) {
      console.error('Failed to update onboarding step:', err);
    }
    next();
  };

  const saveBranding = async () => {
    setSaving(true);
    try {
      await api.put(`/practice/${user?.practice_id}/branding`, branding);
      try {
        await api.patch(`/practices/${user?.practice_id}/onboarding-step`, { onboarding_step: step + 1 });
      } catch (patchErr) {
        console.error('Failed to update onboarding step:', patchErr);
      }
      toast.success('Branding saved');
      next();
    } catch (err) {
      console.error('Failed to save branding:', err);
      toast.error(err?.response?.data?.detail || 'Failed to save branding');
    } finally {
      setSaving(false);
    }
  };

  const saveEmergency = async () => {
    setSaving(true);
    try {
      await api.put(`/practice/${user?.practice_id}/emergency-rules`, emergency);
      try {
        await api.patch(`/practices/${user?.practice_id}/onboarding-step`, { onboarding_step: step + 1 });
      } catch (patchErr) {
        console.error('Failed to update onboarding step:', patchErr);
      }
      toast.success('Emergency rules saved');
      next();
    } catch (err) {
      console.error('Failed to save emergency rules:', err);
      toast.error(err?.response?.data?.detail || 'Failed to save emergency rules');
    } finally {
      setSaving(false);
    }
  };

  const saveRetell = async () => {
    try {
      await api.patch(
        `/practices/${user?.practice_id}/onboarding-step`,
        { onboarding_step: step + 1 }
      );
    } catch (err) {
      console.error('Failed to update onboarding step:', err);
    }
    next();
  };

  const finish = async () => {
    setSaving(true);
    try {
      await api.post(`/practices/${user?.practice_id}/complete-onboarding`);
      await refreshPractice();
      toast.success('Onboarding complete!');
      navigate('/dashboard');
    } catch (err) {
      console.error('Failed to complete onboarding:', err);
      toast.error(err?.response?.data?.detail || 'Failed to complete onboarding');
    } finally {
      setSaving(false);
    }
  };

  const selectedPlanData = WIZARD_PLANS.find((p) => p.id === selectedPlan);

  // ?plan=enterprise / ?plan=elite should never reach the wizard — bounce
  // straight to Contact Sales before anything renders.
  const urlPlan = searchParams.get('plan');
  if (requiresContactSales(urlPlan)) {
    return <Navigate to={`/contact-sales?plan=${urlPlan}`} replace />;
  }

  return (
    <div className="p-6">
      {/* Step Navigation */}
      <div className="flex justify-center gap-2 mb-6 flex-wrap">
        {STEPS.map((s) => (
          <div
            key={s.id}
            className={`px-3 py-1 rounded-full text-sm ${
              step === s.id ? 'bg-blue-600 text-white' : 'bg-gray-200'
            }`}
          >
            {s.name}
          </div>
        ))}
      </div>

      {/* Step 0 — Welcome */}
      {step === 0 && (
        <StepWrapper step={step}>
          <p className="text-gray-700 mb-4">
            Welcome to Dental AI! Let's get your practice set up.
          </p>
          <Button onClick={next}>Get Started</Button>
        </StepWrapper>
      )}

      {/* Step 1 — Account Creation */}
      {step === 1 && (
        <StepWrapper step={step}>
          <div className="space-y-4">
            <div>
              <Label>Full Name</Label>
              <Input
                value={signup.admin_full_name}
                onChange={(e) => {
                  setSignup({ ...signup, admin_full_name: e.target.value });
                  setSignupErrors((prev) => ({ ...prev, admin_full_name: undefined }));
                }}
              />
              {signupErrors.admin_full_name && (
                <p className="text-sm text-red-500 mt-1">{signupErrors.admin_full_name}</p>
              )}
            </div>

            <div>
              <Label>Email</Label>
              <Input
                type="email"
                value={signup.admin_email}
                onChange={(e) => {
                  setSignup({ ...signup, admin_email: e.target.value });
                  setSignupErrors((prev) => ({ ...prev, admin_email: undefined }));
                }}
              />
              {signupErrors.admin_email && (
                <p className="text-sm text-red-500 mt-1">{signupErrors.admin_email}</p>
              )}
            </div>

            <div>
              <Label>Password</Label>
              <Input
                type="password"
                value={signup.admin_password}
                onChange={(e) => {
                  setSignup({ ...signup, admin_password: e.target.value });
                  setSignupErrors((prev) => ({ ...prev, admin_password: undefined }));
                }}
              />
              {signupErrors.admin_password && (
                <p className="text-sm text-red-500 mt-1">{signupErrors.admin_password}</p>
              )}
            </div>

            <div>
              <Label>Contact Phone</Label>
              <Input
                value={signup.contact_phone}
                onChange={(e) =>
                  setSignup({ ...signup, contact_phone: e.target.value })
                }
              />
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={back}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
              <Button onClick={handleAccountCreation} disabled={saving}>
                {saving ? <Loader2 className="animate-spin" /> : 'Continue'}
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Step 2 — Plan Selection */}
      {step === 2 && (
        <StepWrapper step={step}>
          <div className="space-y-6">
            <p className="text-gray-600 text-sm">
              Choose the plan that fits your practice. You can upgrade anytime.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {WIZARD_PLANS.map((plan) => {
                // Only Professional is gated by self-serve availability.
                // Enterprise/Elite keep their existing Contact Sales click
                // regardless — a separate, permanent, human-mediated path.
                const isLocked = plan.id === 'professional' && selfServeTiers?.[plan.id] !== true;
                const salesGated = requiresContactSales(plan.id);
                const isSelected = !salesGated && !isLocked && selectedPlan === plan.id;
                return (
                  <div
                    key={plan.id}
                    aria-disabled={isLocked}
                    className={[
                      'relative rounded-xl p-5 transition-all',
                      isLocked
                        ? 'cursor-not-allowed opacity-60 border border-slate-200 bg-slate-50'
                        : 'cursor-pointer',
                      !isLocked && isSelected
                        ? plan.isElite
                          ? 'bg-yellow-50/60'
                          : 'border-2 border-teal-600 bg-teal-50/40'
                        : !isLocked
                        ? 'border border-slate-200 bg-white hover:border-slate-300'
                        : '',
                    ].join(' ')}
                    style={!isLocked && isSelected && plan.isElite ? { border: '2px solid #D4AF37' } : {}}
                    onClick={() => {
                      if (isLocked) return;
                      if (salesGated) {
                        navigate(`/contact-sales?plan=${plan.id}`);
                      } else {
                        setSelectedPlan(plan.id);
                      }
                    }}
                  >
                    {isLocked ? (
                      <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-[11px] font-semibold whitespace-nowrap bg-slate-400 text-white">
                        Coming Soon
                      </span>
                    ) : plan.badge && (
                      <span
                        className={`absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-[11px] font-semibold whitespace-nowrap ${
                          plan.isElite ? 'text-white' : 'bg-teal-600 text-white'
                        }`}
                        style={plan.isElite ? { backgroundColor: '#D4AF37' } : {}}
                      >
                        {plan.badge}
                      </span>
                    )}

                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <h3
                          className={`font-bold text-base ${
                            isLocked ? 'text-slate-400' : plan.isElite ? 'text-[#b8962f]' : 'text-slate-900'
                          }`}
                        >
                          {plan.name}
                        </h3>
                        <div className="flex items-baseline gap-1 mt-0.5">
                          <span className={`text-xl font-bold ${isLocked ? 'text-slate-400' : 'text-slate-900'}`}>{plan.price}</span>
                          <span className="text-xs text-slate-500">/mo</span>
                        </div>
                      </div>
                      {isLocked ? null : salesGated ? (
                        <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 border border-slate-300 rounded-full px-2 py-1 shrink-0">
                          Contact Sales
                        </span>
                      ) : isSelected && (
                        <span
                          className="w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5"
                          style={plan.isElite ? { backgroundColor: '#D4AF37' } : { backgroundColor: '#0d9488' }}
                        >
                          <Check className="w-3 h-3 text-white" />
                        </span>
                      )}
                    </div>

                    <ul className="space-y-1">
                      {plan.limits.map((limit) => (
                        <li key={limit} className={`flex items-center gap-2 text-sm ${isLocked ? 'text-slate-400' : 'text-slate-600'}`}>
                          <Check
                            className={`w-3.5 h-3.5 shrink-0 ${
                              isLocked ? 'text-slate-300' : plan.isElite ? 'text-[#D4AF37]' : 'text-teal-500'
                            }`}
                          />
                          {limit}
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={back}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
              <Button disabled={!selectedPlan} onClick={next}>
                {selectedPlan
                  ? `Continue with ${selectedPlanData?.name}`
                  : 'Select a plan'}
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Step 3 — Practice Basics */}
      {step === 3 && (
        <StepWrapper step={step}>
          <div className="space-y-4">
            {/* Selected plan indicator */}
            {selectedPlanData && (
              <div className="flex items-center justify-between bg-slate-50 rounded-lg px-4 py-2.5 text-sm">
                <span className="text-slate-700">
                  Selected plan:{' '}
                  <span className="font-semibold text-slate-900">{selectedPlanData.name}</span>
                  {' '}— {selectedPlanData.price}/mo
                </span>
                {!planFromUrl && (
                  <button
                    className="text-teal-600 hover:underline text-xs font-medium ml-3"
                    onClick={() => setStep(2)}
                  >
                    Change
                  </button>
                )}
              </div>
            )}

            <div>
              <Label>Practice Name</Label>
              <Input
                value={signup.practice_name}
                onChange={(e) => {
                  setSignup({ ...signup, practice_name: e.target.value });
                  setSignupErrors((prev) => ({ ...prev, practice_name: undefined }));
                }}
              />
              {signupErrors.practice_name && (
                <p className="text-sm text-red-500 mt-1">{signupErrors.practice_name}</p>
              )}
            </div>

            <div>
              <Label>Contact Phone</Label>
              <Input
                value={signup.contact_phone}
                onChange={(e) =>
                  setSignup({ ...signup, contact_phone: e.target.value })
                }
              />
            </div>

            <div>
              <Label>Province / Territory</Label>
              <select
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm mt-1 focus:outline-none focus:ring-2 focus:ring-teal-500"
                value={signup.province}
                onChange={(e) => {
                  setSignup({ ...signup, province: e.target.value });
                  setSignupErrors((prev) => ({ ...prev, province: undefined }));
                }}
                required
              >
                <option value="">Select province…</option>
                {CANADIAN_PROVINCES.map((p) => (
                  <option key={p.code} value={p.code}>{p.label}</option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Determines which Canadian data region your practice is assigned to.
              </p>
              {signupErrors.province && (
                <p className="text-sm text-red-500 mt-1">{signupErrors.province}</p>
              )}
            </div>

            <div className="border-t border-gray-100 pt-4 space-y-3">
              <div>
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    className="mt-0.5 h-4 w-4 rounded border-gray-300 text-teal-600 focus:ring-teal-500"
                    checked={acceptedTerms}
                    onChange={(e) => {
                      setAcceptedTerms(e.target.checked);
                      setSignupErrors((prev) => ({ ...prev, terms: undefined }));
                    }}
                    required
                  />
                  <span className="text-sm text-gray-700">
                    I agree to the{' '}
                    <a
                      href="/terms"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-teal-600 hover:underline font-medium"
                    >
                      Terms &amp; Conditions
                    </a>
                  </span>
                </label>
                {signupErrors.terms && (
                  <p className="text-sm text-red-500 mt-1">{signupErrors.terms}</p>
                )}
              </div>

              <div>
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    className="mt-0.5 h-4 w-4 rounded border-gray-300 text-teal-600 focus:ring-teal-500"
                    checked={acceptedPrivacy}
                    onChange={(e) => {
                      setAcceptedPrivacy(e.target.checked);
                      setSignupErrors((prev) => ({ ...prev, privacy: undefined }));
                    }}
                    required
                  />
                  <span className="text-sm text-gray-700">
                    I have read and agree to the{' '}
                    <a
                      href="/privacy"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-teal-600 hover:underline font-medium"
                    >
                      Privacy Policy
                    </a>
                  </span>
                </label>
                {signupErrors.privacy && (
                  <p className="text-sm text-red-500 mt-1">{signupErrors.privacy}</p>
                )}
              </div>
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={back}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
              <Button onClick={handlePracticeCreation} disabled={saving}>
                {saving ? <Loader2 className="animate-spin" /> : 'Save & Continue'}
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Step 4 — Hours */}
      {step === 4 && (
        <StepWrapper step={step}>
          <div className="space-y-4">
            {DAY_KEYS.map((day) => (
              <div key={day} className="flex items-center gap-4">
                <Label className="w-16">{DAY_LABELS[day]}</Label>

                {hours.weekly[day] ? (
                  <>
                    <Input
                      type="time"
                      value={hours.weekly[day].open}
                      onChange={(e) =>
                        setHours({
                          ...hours,
                          weekly: {
                            ...hours.weekly,
                            [day]: { ...hours.weekly[day], open: e.target.value },
                          },
                        })
                      }
                    />
                    <Input
                      type="time"
                      value={hours.weekly[day].close}
                      onChange={(e) =>
                        setHours({
                          ...hours,
                          weekly: {
                            ...hours.weekly,
                            [day]: { ...hours.weekly[day], close: e.target.value },
                          },
                        })
                      }
                    />
                    <Button
                      variant="outline"
                      onClick={() =>
                        setHours({ ...hours, weekly: { ...hours.weekly, [day]: null } })
                      }
                    >
                      Closed
                    </Button>
                  </>
                ) : (
                  <Button
                    onClick={() =>
                      setHours({
                        ...hours,
                        weekly: { ...hours.weekly, [day]: { open: '09:00', close: '17:00' } },
                      })
                    }
                  >
                    Set Hours
                  </Button>
                )}
              </div>
            ))}

            <div className="flex justify-between">
              <Button variant="outline" onClick={back}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
              <Button onClick={saveHours} disabled={saving}>
                {saving ? <Loader2 className="animate-spin" /> : 'Save & Continue'}
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Step 5 — Providers */}
      {step === 5 && (
        <StepWrapper step={step}>
          <div className="space-y-4">
            <div className="flex gap-4">
              <Input
                placeholder="Provider Name"
                value={newProvider.name}
                onChange={(e) => setNewProvider({ ...newProvider, name: e.target.value })}
              />
              <Input
                placeholder="Role"
                value={newProvider.role}
                onChange={(e) => setNewProvider({ ...newProvider, role: e.target.value })}
              />
              <Button onClick={addProvider} disabled={saving}>
                Add
              </Button>
            </div>

            <div className="space-y-2">
              {providers.map((p) => (
                <div key={p.id} className="flex justify-between items-center p-2 border rounded">
                  <span>{p.name} — {p.role}</span>
                  <Button variant="destructive" size="sm" onClick={() => removeProvider(p.id)}>
                    Remove
                  </Button>
                </div>
              ))}
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={back}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
              <Button onClick={handleProvidersContinue}>
                Continue
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Step 6 — Appointment Types */}
      {step === 6 && (
        <StepWrapper step={step}>
          <div className="space-y-4">
            <div className="flex gap-4">
              <Input
                placeholder="Type Name"
                value={newType.name}
                onChange={(e) => setNewType({ ...newType, name: e.target.value })}
              />
              <Input
                type="number"
                placeholder="Duration (min)"
                value={newType.duration_min}
                onChange={(e) => setNewType({ ...newType, duration_min: Number(e.target.value) })}
              />
              <Button onClick={addApptType} disabled={saving}>
                Add
              </Button>
            </div>

            <div className="space-y-2">
              {apptTypes.map((t) => (
                <div key={t.id} className="flex justify-between items-center p-2 border rounded">
                  <span>{t.name} — {t.duration_min} min</span>
                  <Button variant="destructive" size="sm" onClick={() => removeApptType(t.id)}>
                    Remove
                  </Button>
                </div>
              ))}
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={back}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
              <Button onClick={handleApptTypesContinue}>
                Continue
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Step 7 — Branding */}
      {step === 7 && (
        <StepWrapper step={step}>
          <div className="space-y-4">
            <div>
              <Label>AI Receptionist Name</Label>
              <Input
                value={branding.agent_name}
                onChange={(e) => setBranding({ ...branding, agent_name: e.target.value })}
              />
            </div>

            <div>
              <Label>Greeting</Label>
              <Input
                placeholder="Hi, thank you for calling..."
                value={branding.greeting}
                onChange={(e) => setBranding({ ...branding, greeting: e.target.value })}
              />
            </div>

            <div>
              <Label>Closing Line</Label>
              <Input
                value={branding.closing}
                onChange={(e) => setBranding({ ...branding, closing: e.target.value })}
              />
            </div>

            <div>
              <Label>Voice Tone</Label>
              <select
                className="border rounded p-2 w-full"
                value={branding.voice_tone}
                onChange={(e) => setBranding({ ...branding, voice_tone: e.target.value })}
              >
                <option value="warm_professional">Warm & Professional</option>
                <option value="friendly">Friendly</option>
                <option value="formal">Formal</option>
                <option value="energetic">Energetic</option>
              </select>
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={back}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
              <Button onClick={saveBranding} disabled={saving}>
                {saving ? <Loader2 className="animate-spin" /> : 'Save & Continue'}
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Step 8 — Emergency Rules */}
      {step === 8 && (
        <StepWrapper step={step}>
          <div className="space-y-4">
            <div>
              <Label>Emergency Trigger Keywords</Label>
              <Input
                value={emergency.triggers.join(', ')}
                onChange={(e) =>
                  setEmergency({
                    ...emergency,
                    triggers: e.target.value.split(',').map((t) => t.trim()),
                  })
                }
              />
            </div>

            <div>
              <Label>Response Policy</Label>
              <select
                className="border rounded p-2 w-full"
                value={emergency.response_policy}
                onChange={(e) =>
                  setEmergency({ ...emergency, response_policy: e.target.value })
                }
              >
                <option value="earliest_available">Earliest Available</option>
                <option value="same_day_if_possible">Same Day If Possible</option>
                <option value="redirect_to_emergency_line">Redirect to Emergency Line</option>
              </select>
            </div>

            <div>
              <Label>After-Hours Emergency Phone</Label>
              <Input
                value={emergency.after_hours_handoff_phone}
                onChange={(e) =>
                  setEmergency({ ...emergency, after_hours_handoff_phone: e.target.value })
                }
              />
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={back}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
              <Button onClick={saveEmergency} disabled={saving}>
                {saving ? <Loader2 className="animate-spin" /> : 'Save & Continue'}
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Step 9 — Retell Setup */}
      {step === 9 && (
        <StepWrapper step={step}>
          <div className="space-y-4">
            <p className="text-gray-700">
              Retell configuration is completed by your Dental AI onboarding team.
              Your agent ID and phone number will be configured before go-live. You
              can update these settings later from your dashboard once your account
              is activated.
            </p>

            <div>
              <Label>Retell Agent ID</Label>
              <Input value={retellAgentId} disabled />
            </div>

            <div>
              <Label>Retell Phone Number</Label>
              <Input value={retellPhone} disabled />
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={back}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
              <Button onClick={saveRetell} disabled={saving}>
                {saving ? <Loader2 className="animate-spin" /> : 'Save & Continue'}
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Step 10 — Test & Finish */}
      {step === 10 && (
        <StepWrapper step={step}>
          <div className="space-y-4">
            <p className="text-gray-700">
              Your practice setup is complete! You can now test your AI receptionist
              and begin using Dental AI.
            </p>

            <Button className="w-full" onClick={finish} disabled={saving}>
              {saving ? <Loader2 className="animate-spin" /> : 'Finish & Go to Dashboard'}
            </Button>

            <Button variant="outline" className="w-full" onClick={() => navigate('/dashboard')}>
              Skip for now
            </Button>
          </div>
        </StepWrapper>
      )}
    </div>
  );
}
