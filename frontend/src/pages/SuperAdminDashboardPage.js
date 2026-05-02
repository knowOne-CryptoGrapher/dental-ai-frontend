import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import {
  Building2, Users, Calendar, Phone, ShieldCheck, AlertTriangle,
  Zap, Loader2, Plus, ArrowRight, CreditCard, Tag,
} from 'lucide-react';
import { toast } from 'sonner';

function StatCard({ icon: Icon, label, value, sublabel, accent = 'amber', testId }) {
  const colors = {
    amber: 'from-amber-500/10 to-amber-500/0 border-amber-500/20 text-amber-300',
    teal: 'from-teal-500/10 to-teal-500/0 border-teal-500/20 text-teal-300',
    red: 'from-red-500/10 to-red-500/0 border-red-500/20 text-red-300',
    violet: 'from-violet-500/10 to-violet-500/0 border-violet-500/20 text-violet-300',
  };
  return (
    <div
      data-testid={testId}
      className={`relative overflow-hidden rounded-xl border bg-gradient-to-br ${colors[accent]} p-5`}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">{label}</p>
          <p className="text-3xl font-bold text-white mt-2 tabular-nums">{value}</p>
          {sublabel && <p className="text-xs text-slate-500 mt-1">{sublabel}</p>}
        </div>
        <Icon className={`w-7 h-7 ${colors[accent].split(' ').pop()}`} />
      </div>
    </div>
  );
}

export default function SuperAdminDashboardPage() {
  const { axiosAuth } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const r = await axiosAuth().get('/superadmin/dashboard');
        setData(r.data);
      } catch (e) {
        toast.error(e.response?.data?.detail || 'Failed to load dashboard');
      } finally {
        setLoading(false);
      }
    })();
  }, [axiosAuth]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />
      </div>
    );
  }

  const p = data?.practices || {};
  const pl = data?.platform || {};

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto" data-testid="superadmin-dashboard">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-8">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-amber-400">Platform Operations</p>
          <h1 className="text-3xl font-bold text-white mt-1">Welcome back, owner.</h1>
          <p className="text-sm text-slate-400 mt-2 max-w-2xl">
            Infrastructure dashboard for the entire DentalAI fleet. Below is the pulse of every clinic running on the platform.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            data-testid="dash-create-practice-btn"
            onClick={() => navigate('/admin/practices?new=1')}
            className="bg-gradient-to-r from-red-500 to-amber-500 hover:from-red-400 hover:to-amber-400 text-white border-0"
          >
            <Plus className="w-4 h-4 mr-1.5" /> Create New Practice
          </Button>
        </div>
      </div>

      {!data?.automation_available && (
        <div className="mb-6 flex items-start gap-3 p-4 rounded-lg bg-amber-500/5 border border-amber-500/20" data-testid="automation-banner">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-semibold text-amber-200">Retell automation is in manual mode</p>
            <p className="text-slate-400 mt-1">
              Set <code className="px-1.5 py-0.5 bg-slate-800 rounded text-amber-300 text-xs">RETELL_API_KEY</code> in <code className="px-1.5 py-0.5 bg-slate-800 rounded text-amber-300 text-xs">backend/.env</code> to unlock one-click agent provisioning.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard testId="stat-practices" icon={Building2} label="Practices" value={p.total ?? 0} sublabel={`${p.active ?? 0} active · ${p.onboarding ?? 0} onboarding`} accent="amber" />
        <StatCard testId="stat-provisioned" icon={ShieldCheck} label="Retell Provisioned" value={p.retell_provisioned ?? 0} sublabel={`${(p.total ?? 0) - (p.retell_provisioned ?? 0)} need setup`} accent="teal" />
        <StatCard testId="stat-calls" icon={Phone} label="Calls (30d)" value={pl.calls_last_30_days ?? 0} sublabel="Across all clinics" accent="violet" />
        <StatCard testId="stat-suspended" icon={AlertTriangle} label="Suspended" value={p.suspended ?? 0} sublabel="Billing or compliance hold" accent="red" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
        <StatCard testId="stat-patients" icon={Users} label="Total patients" value={pl.total_patients ?? 0} accent="teal" />
        <StatCard testId="stat-appointments" icon={Calendar} label="Total appointments" value={pl.total_appointments ?? 0} accent="violet" />
        <StatCard testId="stat-users" icon={Users} label="Total platform users" value={pl.total_users ?? 0} accent="amber" />
      </div>

      <Card className="bg-slate-900 border-slate-800">
        <CardHeader className="border-b border-slate-800">
          <div className="flex items-center justify-between">
            <CardTitle className="text-slate-100 text-base flex items-center gap-2">
              <Zap className="w-4 h-4 text-amber-400" /> Recent practices
            </CardTitle>
            <Button
              data-testid="dash-view-all-practices"
              variant="ghost"
              size="sm"
              onClick={() => navigate('/admin/practices')}
              className="text-amber-300 hover:text-amber-200 hover:bg-amber-500/10"
            >
              View all <ArrowRight className="w-3.5 h-3.5 ml-1" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {(data?.recent_practices?.length ?? 0) === 0 ? (
            <div className="p-12 text-center text-slate-500 text-sm" data-testid="recent-empty">
              No practices yet. Create the first one to get started.
            </div>
          ) : (
            <div className="divide-y divide-slate-800">
              {data.recent_practices.map(rp => (
                <div key={rp.id} className="px-5 py-3 flex items-center justify-between hover:bg-slate-800/40 transition" data-testid={`recent-row-${rp.id}`}>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-100 truncate">{rp.name}</p>
                    <p className="text-[11px] text-slate-500 truncate">{rp.id}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {rp.retell_provisioned
                      ? <Badge className="bg-teal-500/15 text-teal-300 border border-teal-500/30 hover:bg-teal-500/15">Provisioned</Badge>
                      : <Badge className="bg-amber-500/15 text-amber-300 border border-amber-500/30 hover:bg-amber-500/15">Needs setup</Badge>}
                    <Badge variant="outline" className={`text-[10px] uppercase tracking-wider border-slate-700 ${
                      rp.status === 'active' ? 'text-teal-300' : rp.status === 'suspended' ? 'text-red-300' : 'text-amber-300'
                    }`}>{rp.status}</Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Plan distribution + Failed payments ───────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-4">
        <Card className="bg-slate-900 border-slate-800" data-testid="plan-distribution-card">
          <CardHeader className="border-b border-slate-800">
            <CardTitle className="text-slate-100 text-base flex items-center gap-2">
              <Tag className="w-4 h-4 text-violet-400" /> Plan distribution
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {Object.keys(data?.plan_distribution || {}).length === 0 ? (
              <p className="p-8 text-sm text-slate-500 text-center">No active subscriptions yet.</p>
            ) : (
              <div className="divide-y divide-slate-800">
                {Object.entries(data.plan_distribution || {}).map(([plan, n]) => (
                  <div key={plan} className="px-5 py-3 flex items-center justify-between">
                    <span className="text-sm font-mono text-violet-300 capitalize">{plan}</span>
                    <Badge variant="outline" className="border-slate-700 text-slate-200 tabular-nums">{n}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800" data-testid="failed-payments-card">
          <CardHeader className="border-b border-slate-800">
            <div className="flex items-center justify-between">
              <CardTitle className="text-slate-100 text-base flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-red-400" /> Failed payments
              </CardTitle>
              <Badge className="bg-red-500/15 text-red-300 border border-red-500/30 hover:bg-red-500/15 tabular-nums">
                {(data?.practices?.past_due ?? 0) + (data?.practices?.cancelled_subscriptions ?? 0)}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {(data?.failed_payments?.length ?? 0) === 0 ? (
              <p className="p-8 text-sm text-slate-500 text-center" data-testid="failed-payments-empty">
                All clinics paid. Well done.
              </p>
            ) : (
              <div className="divide-y divide-slate-800 max-h-[320px] overflow-y-auto">
                {data.failed_payments.map(fp => (
                  <div
                    key={fp.id}
                    data-testid={`failed-payment-${fp.id}`}
                    className="px-5 py-3 flex items-center justify-between hover:bg-slate-800/40 cursor-pointer transition"
                    onClick={() => navigate(`/admin/practices?search=${encodeURIComponent(fp.name || '')}`)}
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-100 truncate">{fp.name}</p>
                      <p className="text-[11px] text-slate-500 truncate">
                        {fp.contact_email || fp.id}
                        {fp.subscription_plan && <span className="text-violet-300 ml-2">· {fp.subscription_plan}</span>}
                      </p>
                      {fp.billing_status_updated_at && (
                        <p className="text-[10px] text-slate-600 mt-0.5">
                          Since {new Date(fp.billing_status_updated_at).toLocaleString()}
                        </p>
                      )}
                    </div>
                    <Badge className={`text-[10px] uppercase tracking-wider border ${
                      fp.billing_status === 'past_due'
                        ? 'border-red-500/40 text-red-300 bg-red-500/10'
                        : 'border-amber-500/40 text-amber-300 bg-amber-500/10'
                    } hover:bg-red-500/10 shrink-0`}>{fp.billing_status}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
