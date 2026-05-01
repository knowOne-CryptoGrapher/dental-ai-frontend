import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import {
  CreditCard, Check, Phone, MapPin, Briefcase, FileText, Loader2,
  ExternalLink, AlertCircle, Sparkles,
} from 'lucide-react';

const POLL_INTERVAL_MS = 2000;
const POLL_MAX_ATTEMPTS = 12;

export default function BillingPage() {
  const { axiosAuth } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [plans, setPlans] = useState([]);
  const [usage, setUsage] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyPlan, setBusyPlan] = useState(null);
  const [openingPortal, setOpeningPortal] = useState(false);

  const [returnState, setReturnState] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const api = axiosAuth();
      const [planRes, usageRes, invRes] = await Promise.all([
        api.get('/billing/plans'),
        api.get('/billing/usage'),
        api.get('/billing/invoices'),
      ]);
      setPlans(planRes.data || []);
      setUsage(usageRes.data);
      setInvoices(invRes.data || []);
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

  return (
    <div className="space-y-6 max-w-5xl" data-testid="billing-page">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Billing & Usage</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage your subscription, view invoices, and update your payment method.
          </p>
        </div>
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

      {/* Plans */}
      <div>
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Available plans</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {plans.map(plan => {
            const isCurrent = usage?.plan === plan.id && hasCustomer;
            const isElite = plan.id === 'elite';

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

                    {isElite && (
                      <Badge className="bg-yellow-100 text-yellow-800 text-[10px]">
                        Most Advanced
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
                  </ul>

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
                        : <><CreditCard className="w-3.5 h-3.5 mr-1.5" /> Subscribe</>}
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

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
