import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useFeatures } from '../hooks/useFeatures';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import {
  CreditCard, Check, Phone, MapPin, Briefcase, FileText, Loader2,
  ExternalLink, AlertCircle, Sparkles, Headphones, ShieldCheck, Download,
  Brain, ArrowRight, LayoutGrid, X, Users,
} from 'lucide-react';
import ComparePlansModal from '../components/ComparePlansModal';
import ContactSalesModal from '../components/sales/ContactSalesModal';

const CONTACT_SALES_PLANS = ['enterprise', 'elite'];
const requiresContactSales = (planId) => CONTACT_SALES_PLANS.includes(planId);

const POLL_INTERVAL_MS = 2000;
const POLL_MAX_ATTEMPTS = 12;

const METRIC_LABELS = {
  calls:     'Voice Call',
  providers: 'Provider',
  locations: 'Location',
  users:     'User',
};

const USAGE_METRICS = [
  { key: 'calls',     label: 'Voice Calls this month' },
  { key: 'providers', label: 'Providers'               },
  { key: 'locations', label: 'Locations'               },
  { key: 'users',     label: 'Users'                   },
];

const PLAN_FEATURE_COPY = {
  basic: {
    prefix: null,
    highlights: [
      'Voice AI',
      'Appointments',
      'Patients',
      'Calendar',
      'Call Logs',
      'Audit Logs',
    ],
  },
  professional: {
    prefix: 'Everything in Basic, plus:',
    highlights: [
      'Analytics',
      'Insurance / CDAnet',
      'Multi-Location',
    ],
  },
  enterprise: {
    prefix: 'Everything in Professional, plus:',
    highlights: [
      'Custom Voice',
      'Knowledge Base',
      'Routing Rules',
    ],
  },
  elite: {
    prefix: 'Everything in Enterprise, plus:',
    highlights: [
      'Dedicated Support SLA',
      'HIPAA / PIPEDA BAA',
      'Custom Model Selection',
    ],
  },
};

export default function BillingPage() {
  const { axiosAuth } = useAuth();
  const { has, featuresLoading } = useFeatures();
  const [searchParams, setSearchParams] = useSearchParams();

  const [plans, setPlans] = useState([]);
  const [usage, setUsage] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyPlan, setBusyPlan] = useState(null);
  const [openingPortal, setOpeningPortal] = useState(false);
  const [baaLoading, setBaaLoading] = useState(false);
  const [baaError, setBaaError] = useState('');
  const [comparePlansOpen, setComparePlansOpen] = useState(false);
  const [salesModal, setSalesModal] = useState({ open: false, plan: 'enterprise' });
  const [usageStats, setUsageStats] = useState(null);
  const [usageBannerDismissed, setUsageBannerDismissed] = useState(false);

  const [returnState, setReturnState] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const api = axiosAuth();
      const [planRes, usageRes, invRes, statsRes] = await Promise.all([
        api.get('/billing/plans'),
        api.get('/billing/usage'),
        api.get('/billing/invoices'),
        api.get('/billing/usage-stats').catch(() => ({ data: null })),
      ]);
      setPlans(planRes.data || []);
      setUsage(usageRes.data);
      setInvoices(invRes.data || []);
      setUsageStats(statsRes.data);
    } catch (e) {
      console.error(e);
      toast.error('Failed to load billing info');
    } finally {
      setLoading(false);
    }
  }, [axiosAuth]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // ── Handle return-from-Stripe ───────────────────────────────────────
  useEffect(() => {
    const sid = searchParams.get('session_id');
    const cancelled = searchParams.get('stripe') === 'cancelled';

    if (cancelled) {
      setReturnState('cancelled');
      toast.info('Checkout cancelled');
      const next = new URLSearchParams(searchParams);
      next.delete('stripe'); setSearchParams(next, { replace: true });
      return;
    }
    if (!sid) return;

    setReturnState('polling');
    let cancelledFlag = false;
    let attempts = 0;
    const api = axiosAuth();

    const tick = async () => {
      if (cancelledFlag) return;
      attempts += 1;
      try {
        const r = await api.get(`/billing/checkout/status/${sid}`);
        if (r.data.payment_status === 'paid') {
          setReturnState('paid');
          toast.success(`You're on the ${r.data.plan_id} plan.`);
          await fetchAll();
          const next = new URLSearchParams(searchParams);
          next.delete('session_id'); setSearchParams(next, { replace: true });
          return;
        }
        if (attempts >= POLL_MAX_ATTEMPTS) {
          setReturnState('timeout');
          toast.warning('Still confirming with Stripe — refresh in a moment.');
          return;
        }
        setTimeout(tick, POLL_INTERVAL_MS);
      } catch (e) {
        console.error('Poll error:', e);
        if (attempts < POLL_MAX_ATTEMPTS) setTimeout(tick, POLL_INTERVAL_MS);
        else setReturnState('timeout');
      }
    };
    tick();
    return () => { cancelledFlag = true; };
  }, [searchParams, axiosAuth, fetchAll, setSearchParams]);

  // ── Actions ─────────────────────────────────────────────────────────
  const subscribe = async (planId) => {
    if (requiresContactSales(planId)) {
      setSalesModal({ open: true, plan: planId });
      return;
    }
    setBusyPlan(planId);
    try {
      const api = axiosAuth();
      const r = await api.post('/billing/checkout', {
        plan: planId,
        origin_url: window.location.origin,
      });
      if (r.data.url) {
        window.location.href = r.data.url;
      } else {
        toast.error('Could not start checkout');
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Checkout failed');
    } finally {
      setBusyPlan(null);
    }
  };

  const downloadBaa = async () => {
    setBaaLoading(true);
    setBaaError('');
    try {
      const response = await axiosAuth().get('/billing/baa', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'BAA-DentalAI.pdf');
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch {
      setBaaError('Failed to download BAA. Please try again.');
    } finally {
      setBaaLoading(false);
    }
  };

  const openPortal = async () => {
    setOpeningPortal(true);
    try {
      const api = axiosAuth();
      const r = await api.post('/billing/portal', {
        origin_url: window.location.origin,
      });
      if (r.data.url) window.open(r.data.url, '_blank');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Could not open billing portal');
    } finally {
      setOpeningPortal(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="w-6 h-6 text-teal-600 animate-spin" />
      </div>
    );
  }

  const hasCustomer = !!usage?.stripe_customer_id;
  const billingStatus = usage?.billing_status || 'active';
  const atLimitMetric = usageStats
    ? ['calls', 'providers', 'locations', 'users'].find(
        k => (usageStats[k]?.used ?? 0) >= (usageStats[k]?.limit ?? Infinity)
      )
    : null;

  return (
    <div className="space-y-6 max-w-5xl" data-testid="billing-page">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Billing & Usage</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage your subscription, view invoices, and update your payment method.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setComparePlansOpen(true)}
            className="border-gray-200 text-gray-600 hover:bg-gray-50"
          >
            <LayoutGrid className="w-4 h-4 mr-1.5" />
            Compare Plans
          </Button>
          {hasCustomer && (
            <Button
              data-testid="manage-billing-btn"
              onClick={openPortal}
              disabled={openingPortal}
              variant="outline"
              className="border-teal-200 text-teal-700 hover:bg-teal-50"
            >
              {openingPortal ? <Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> : <ExternalLink className="w-4 h-4 mr-1.5" />}
              Manage Billing
            </Button>
          )}
        </div>
      </div>

      {/* Return-from-Stripe banners */}
      {returnState === 'polling' && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-blue-50 border border-blue-200">
          <Loader2 className="w-5 h-5 text-blue-600 animate-spin shrink-0" />
          <div className="text-sm text-blue-900">Confirming payment with Stripe…</div>
        </div>
      )}
      {returnState === 'paid' && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-emerald-50 border border-emerald-200">
          <Check className="w-5 h-5 text-emerald-600 shrink-0" />
          <div className="text-sm text-emerald-900 font-medium">Payment confirmed — you're all set.</div>
        </div>
      )}
      {returnState === 'cancelled' && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-amber-50 border border-amber-200">
          <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
          <div className="text-sm text-amber-900">Checkout cancelled. No charges were made.</div>
        </div>
      )}
      {returnState === 'timeout' && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-amber-50 border border-amber-200">
          <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
          <div className="text-sm text-amber-900">Still waiting on Stripe — refresh this page in a moment.</div>
        </div>
      )}

      {/* Past-due alert */}
      {billingStatus === 'past_due' && (
        <div className="flex items-center gap-3 p-4 rounded-lg bg-red-50 border border-red-200">
          <AlertCircle className="w-5 h-5 text-red-600 shrink-0" />
          <div className="text-sm text-red-900">
            Your last payment failed. Click <strong>Manage Billing</strong> to update your card.
          </div>
        </div>
      )}

      {/* Limit reached banner */}
      {!usageBannerDismissed && atLimitMetric && (
        <div className="flex items-center justify-between gap-4 p-4 rounded-lg bg-red-50 border border-red-200">
          <div className="flex items-center gap-3 min-w-0">
            <AlertCircle className="w-5 h-5 text-red-600 shrink-0" />
            <p className="text-sm text-red-900">
              You've reached your <strong>{METRIC_LABELS[atLimitMetric]}</strong> limit.{' '}
              Upgrade your plan to continue growing.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button
              size="sm"
              variant="outline"
              className="border-red-200 text-red-700 hover:bg-red-50"
              onClick={() => setComparePlansOpen(true)}
            >
              View Plans
            </Button>
            <button
              onClick={() => setUsageBannerDismissed(true)}
              className="p-1 text-red-400 hover:text-red-600 transition-colors"
              aria-label="Dismiss"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Current Plan */}
      {usage && (
        <Card className="border-gray-200/80 border-l-4 border-l-teal-500">
          <CardContent className="p-5">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wide">Current Plan</p>
                <p className="text-2xl font-bold text-gray-900">
                  {usage.plan_name}
                  <span className="text-base font-normal text-gray-500 ml-2">${usage.price}/mo</span>
                </p>
                <Badge variant="outline" className={`mt-1 text-[10px] uppercase tracking-wider ${
                  billingStatus === 'active' ? 'border-emerald-200 text-emerald-700' :
                  billingStatus === 'past_due' ? 'border-red-200 text-red-700' :
                  'border-amber-200 text-amber-700'
                }`}>{billingStatus}</Badge>
              </div>
              <div className="flex gap-6 text-sm">
                <div className="text-center">
                  <p className="text-lg font-bold">{usage.usage?.calls?.used || 0}</p>
                  <p className="text-xs text-gray-500">/{usage.usage?.calls?.included} calls</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-bold">{usage.usage?.providers?.used || 0}</p>
                  <p className="text-xs text-gray-500">/{usage.usage?.providers?.max} providers</p>
                </div>
                <div className="text-center">
                  <p className="text-lg font-bold">{usage.usage?.locations?.used || 0}</p>
                  <p className="text-xs text-gray-500">/{usage.usage?.locations?.max} locations</p>
                </div>
              </div>
            </div>
            {!hasCustomer && (
              <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 px-2.5 py-1.5 rounded mt-3 inline-flex items-center gap-1.5">
                <Sparkles className="w-3 h-3" />
                Subscribe below to activate Stripe billing and unlock the customer portal.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Plan Usage */}
      {usageStats && (
        <Card className="border-gray-200/80">
          <CardContent className="p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">Plan Usage</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              {USAGE_METRICS.map(({ key, label }) => {
                const stat = usageStats[key];
                if (!stat) return null;
                const pct = stat.limit > 0 ? Math.min((stat.used / stat.limit) * 100, 100) : 0;
                const isAtLimit = stat.used >= stat.limit;
                const isWarning = !isAtLimit && pct >= 80;
                const barColor  = isAtLimit ? 'bg-red-500'   : isWarning ? 'bg-amber-400' : 'bg-teal-500';
                const trackColor = isAtLimit ? 'bg-red-100'  : isWarning ? 'bg-amber-100' : 'bg-gray-100';
                return (
                  <div key={key}>
                    <div className="flex items-center justify-between mb-1.5 gap-2">
                      <span className="text-[13px] text-gray-600">{label}</span>
                      {isAtLimit && (
                        <button
                          onClick={() => setComparePlansOpen(true)}
                          className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-red-100 text-red-700 hover:bg-red-200 transition-colors shrink-0"
                        >
                          Limit reached — upgrade to get more
                        </button>
                      )}
                      {isWarning && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 shrink-0">
                          Approaching limit
                        </span>
                      )}
                    </div>
                    <div className={`w-full ${trackColor} rounded-full h-2 overflow-hidden`}>
                      <div
                        className={`h-full ${barColor} rounded-full transition-all duration-500`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <p className="text-[11px] text-gray-400 mt-1.5">
                      {stat.used.toLocaleString()} of {stat.limit.toLocaleString()} used
                    </p>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Elite upsell — shown to non-Elite plans only */}
      {usage && usage.plan !== 'elite' && (
        <div className="rounded-xl border border-[#D4AF37]/40 bg-gradient-to-b from-yellow-50/60 to-white p-5">
          <div className="flex items-start justify-between gap-4 flex-wrap mb-4">
            <div>
              <h2 className="text-base font-bold text-gray-900">Unlock Elite Features</h2>
              <p className="text-sm text-gray-500 mt-0.5">Everything in Enterprise, plus:</p>
            </div>
            <Button
              className="bg-[#D4AF37] hover:bg-[#b8962f] text-white gap-1.5 shrink-0"
              onClick={() => { window.location.href = 'mailto:sales@dentalai.ca'; }}
            >
              Upgrade to Elite — $1,499/mo
              <ArrowRight className="w-4 h-4" aria-hidden="true" />
            </Button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              {
                icon: Headphones,
                title: 'Dedicated Support SLA',
                description: '4-hour response SLA with a named CSM.',
              },
              {
                icon: ShieldCheck,
                title: 'HIPAA / PIPEDA BAA',
                description: 'Downloadable Business Associate Agreement for full compliance.',
              },
              {
                icon: Brain,
                title: 'Custom Model Selection',
                description: 'Choose GPT-4o, GPT-4o mini, or Claude Sonnet for your practice.',
              },
            ].map(({ icon: Icon, title, description }) => (
              <div key={title} className="flex items-start gap-3 p-3 rounded-lg bg-white/80 border border-yellow-100">
                <div className="w-8 h-8 rounded-full bg-yellow-50 flex items-center justify-center shrink-0">
                  <Icon className="w-4 h-4 text-[#b8962f]" aria-hidden="true" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-gray-900">{title}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Plans */}
      <div>
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Available plans</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {plans.map(plan => {
            const isCurrent = usage?.plan === plan.id && hasCustomer;
            const isElite = plan.id === 'elite';
            const isProfessional = plan.id === 'professional';

            return (
              <Card
                key={plan.id}
                data-testid={`plan-card-${plan.id}`}
                className={`
                  border-gray-200/80 transition-all
                  ${isCurrent && !isElite ? 'ring-2 ring-teal-300' : ''}
                  ${isElite ? 'ring-2 ring-[#D4AF37] bg-gradient-to-b from-yellow-50 to-white shadow-[0_0_12px_rgba(212,175,55,0.25)]' : ''}
                  ${isCurrent && isElite ? 'ring-2 ring-[#D4AF37]' : ''}
                  hover:shadow-md
                `}
              >
                <CardContent className="p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-base font-bold text-gray-900">{plan.name}</h3>

                    {isElite && !isCurrent && (
                      <Badge className="bg-yellow-100 text-yellow-800 text-[10px]">
                        Most Powerful
                      </Badge>
                    )}

                    {isProfessional && !isCurrent && (
                      <Badge className="bg-teal-600 text-white text-[10px]">
                        Most Popular
                      </Badge>
                    )}

                    {isCurrent && !isElite && (
                      <Badge className="bg-teal-100 text-teal-700 text-[10px]">Current</Badge>
                    )}

                    {isCurrent && isElite && (
                      <Badge className="bg-yellow-100 text-yellow-800 text-[10px]">Current</Badge>
                    )}
                  </div>

                  <p className={`text-3xl font-bold ${isElite ? 'text-[#D4AF37]' : 'text-gray-900'}`}>
                    ${plan.price_usd}<span className="text-sm font-normal text-gray-500">/mo</span>
                  </p>

                  <ul className="mt-3 space-y-1.5 text-sm text-gray-600">
                    <li className="flex items-center gap-2"><Phone className="w-3.5 h-3.5 text-teal-500" />{plan.calls_included} AI calls / mo</li>
                    <li className="flex items-center gap-2"><Briefcase className="w-3.5 h-3.5 text-teal-500" />{plan.providers_max} providers</li>
                    <li className="flex items-center gap-2"><MapPin className="w-3.5 h-3.5 text-teal-500" />{plan.locations_max} locations</li>
                    <li className="flex items-center gap-2"><Users className="w-3.5 h-3.5 text-teal-500" />{plan.users_max} users</li>
                  </ul>

                  {PLAN_FEATURE_COPY[plan.id] && (
                    <div className="mt-3 pt-3 border-t border-gray-100/80">
                      {PLAN_FEATURE_COPY[plan.id].prefix && (
                        <p className="text-[10px] text-gray-400 mb-1.5">{PLAN_FEATURE_COPY[plan.id].prefix}</p>
                      )}
                      <ul className="space-y-1">
                        {PLAN_FEATURE_COPY[plan.id].highlights.map(f => (
                          <li key={f} className="flex items-center gap-1.5 text-[11px] text-gray-600">
                            <Check className="w-3 h-3 text-teal-500 shrink-0" />
                            {f}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {!plan.recurring && (
                    <p className="text-[10px] text-amber-700 mt-2">
                      One-time charge mode (set <code>STRIPE_PRICE_{plan.id.toUpperCase()}</code> for true recurring).
                    </p>
                  )}

                  {!isCurrent && (
                    <Button
                      data-testid={`subscribe-${plan.id}`}
                      className={`
                        w-full mt-4
                        ${isElite
                          ? 'bg-[#D4AF37] hover:bg-[#b8962f] text-white'
                          : 'bg-teal-600 hover:bg-teal-700'
                        }
                      `}
                      size="sm"
                      onClick={() => subscribe(plan.id)}
                      disabled={busyPlan !== null}
                    >
                      {busyPlan === plan.id
                        ? <Loader2 className="w-4 h-4 animate-spin" />
                        : requiresContactSales(plan.id)
                        ? <>Contact Sales</>
                        : <><CreditCard className="w-3.5 h-3.5 mr-1.5" /> Subscribe</>}
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Elite Features */}
      {!featuresLoading && (has('dedicated_support') || has('baa_available')) && (
        <div>
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Elite features</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

            {has('dedicated_support') && (
              <Card className="border-gray-200/80">
                <CardContent className="p-5">
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-full bg-teal-50 flex items-center justify-center shrink-0">
                      <Headphones className="w-5 h-5 text-teal-600" aria-hidden="true" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="text-sm font-semibold text-gray-900">Dedicated Support</p>
                        <Badge className="bg-teal-50 text-teal-700 text-[10px]">Elite</Badge>
                      </div>
                      <p className="text-xs text-gray-500 leading-relaxed">
                        Priority response within 4 hours. Direct access to your named Customer
                        Success Manager.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {has('baa_available') && (
              <Card className="border-gray-200/80">
                <CardContent className="p-5">
                  <div className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-full bg-teal-50 flex items-center justify-center shrink-0">
                      <ShieldCheck className="w-5 h-5 text-teal-600" aria-hidden="true" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <p className="text-sm font-semibold text-gray-900">HIPAA / PIPEDA Compliance Package</p>
                        <Badge className="bg-teal-50 text-teal-700 text-[10px]">Elite</Badge>
                      </div>
                      <p className="text-xs text-gray-500 leading-relaxed mb-3">
                        Download your Business Associate Agreement. Required for HIPAA and PIPEDA
                        compliance.
                      </p>
                      {baaError && (
                        <p className="text-xs text-red-600 mb-2">{baaError}</p>
                      )}
                      <Button
                        size="sm"
                        className="bg-teal-600 hover:bg-teal-700"
                        onClick={downloadBaa}
                        disabled={baaLoading}
                      >
                        {baaLoading
                          ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />
                          : <Download className="w-3.5 h-3.5 mr-1.5" />}
                        Download BAA
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

          </div>
        </div>
      )}

      <ComparePlansModal
        isOpen={comparePlansOpen}
        onClose={() => setComparePlansOpen(false)}
        currentPlan={usage?.plan}
      />

      <ContactSalesModal
        isOpen={salesModal.open}
        onClose={() => setSalesModal(m => ({ ...m, open: false }))}
        requestedPlan={salesModal.plan}
      />

      {/* Invoices */}
      <Card className="border-gray-200/80">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Invoice History</CardTitle>
        </CardHeader>
        <CardContent>
          {invoices.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">No invoices yet.</p>
          ) : (
            <div className="space-y-2">
              {invoices.map(inv => (
                <div key={inv.id} className="flex items-center justify-between p-3 rounded-lg bg-gray-50/80">
                  <div className="flex items-center gap-3 min-w-0">
                    <FileText className="w-4 h-4 text-gray-400 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{inv.period}</p>
                      <p className="text-xs text-gray-500 truncate">
                        {inv.hosted_invoice_url
                          ? <a href={inv.hosted_invoice_url} target="_blank" rel="noopener noreferrer" className="text-teal-600 hover:underline">View on Stripe</a>
                          : inv.id}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-sm font-semibold">${inv.amount.toFixed(2)}</span>
                    <Badge variant="outline" className={
                      inv.status === 'paid' ? 'bg-emerald-50 text-emerald-700' :
                      inv.status === 'open' ? 'bg-amber-50 text-amber-700' :
                      'bg-gray-50 text-gray-700'
                    }>{inv.status}</Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
