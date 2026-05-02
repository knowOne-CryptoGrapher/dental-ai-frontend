import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription,
} from '../components/ui/dialog';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { toast } from 'sonner';
import {
  Plus, Loader2, Search, Building2, Phone, Pause, Play, RefreshCw, UserCog, Tag,
} from 'lucide-react';

const EMPTY_FORM = {
  practice_name: '',
  contact_email: '',
  contact_phone: '',
  timezone: 'America/Toronto',
  admin_email: '',
  admin_password: '',
  admin_full_name: '',
};

export default function SuperAdminPracticesPage() {
  const { axiosAuth, startImpersonation } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [practices, setPractices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  const [confirmAction, setConfirmAction] = useState(null); // { practiceId, type: 'suspend'|'activate' }
  const [impersonatingId, setImpersonatingId] = useState(null);

  // Plan editor — { practiceId, currentPlan }
  const [planEditor, setPlanEditor] = useState(null);
  const [plans, setPlans] = useState([]);
  const [savingPlan, setSavingPlan] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [a, b] = await Promise.all([
        axiosAuth().get('/superadmin/practices'),
        axiosAuth().get('/superadmin/plans'),
      ]);
      setPractices(a.data.practices || []);
      setPlans(b.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load practices');
    } finally {
      setLoading(false);
    }
  }, [axiosAuth]);

  useEffect(() => { load(); }, [load]);

  // Open create modal automatically if ?new=1
  useEffect(() => {
    if (searchParams.get('new') === '1') {
      setDialogOpen(true);
      searchParams.delete('new');
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const filtered = practices.filter(p => {
    if (!search.trim()) return true;
    const q = search.trim().toLowerCase();
    return (
      p.name?.toLowerCase().includes(q) ||
      p.contact_email?.toLowerCase().includes(q) ||
      p.id?.toLowerCase().includes(q)
    );
  });

  const submitCreate = async () => {
    const required = ['practice_name', 'contact_email', 'admin_email', 'admin_password', 'admin_full_name'];
    for (const k of required) {
      if (!form[k]?.trim()) return toast.error(`Missing field: ${k.replace('_', ' ')}`);
    }
    if (form.admin_password.length < 8) return toast.error('Admin password must be at least 8 characters');

    setSubmitting(true);
    try {
      const r = await axiosAuth().post('/superadmin/practices', form);
      toast.success(`Practice created — admin: ${r.data.admin_email}`);
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create practice');
    } finally {
      setSubmitting(false);
    }
  };

  const runSuspendOrActivate = async () => {
    if (!confirmAction) return;
    const { practiceId, type } = confirmAction;
    try {
      await axiosAuth().post(`/superadmin/practices/${practiceId}/${type}`);
      toast.success(`Practice ${type === 'suspend' ? 'suspended' : 'activated'}`);
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed');
    } finally {
      setConfirmAction(null);
    }
  };

  const onImpersonate = async (practice) => {
    setImpersonatingId(practice.id);
    try {
      const res = await startImpersonation(practice.id);
      toast.success(`Impersonating ${res.target_practice?.name || practice.name}`);
      navigate('/dashboard');
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to start impersonation');
      setImpersonatingId(null);
    }
  };

  const savePlan = async () => {
    if (!planEditor) return;
    setSavingPlan(true);
    try {
      await axiosAuth().post(`/superadmin/practices/${planEditor.practiceId}/plan`, {
        plan_id: planEditor.newPlan,
        reason: planEditor.reason || 'super-admin manual override',
      });
      toast.success(`Plan set to ${planEditor.newPlan}`);
      setPlanEditor(null);
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to set plan');
    } finally {
      setSavingPlan(false);
    }
  };

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto" data-testid="superadmin-practices">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-6">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-amber-400">Platform Operations</p>
          <h1 className="text-3xl font-bold text-white mt-1">Manage Practices</h1>
          <p className="text-sm text-slate-400 mt-2 max-w-2xl">
            Every clinic running on the platform. Create, suspend, or jump into Retell setup for any one of them.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={load}
            disabled={loading}
            className="border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800 hover:text-white"
            data-testid="practices-refresh-btn"
          >
            <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </Button>
          <Button
            data-testid="practices-create-btn"
            onClick={() => setDialogOpen(true)}
            className="bg-gradient-to-r from-red-500 to-amber-500 hover:from-red-400 hover:to-amber-400 text-white border-0"
          >
            <Plus className="w-4 h-4 mr-1.5" /> Create New Practice
          </Button>
        </div>
      </div>

      <Card className="bg-slate-900 border-slate-800">
        <CardHeader className="border-b border-slate-800 flex flex-row items-center justify-between">
          <CardTitle className="text-slate-100 text-base flex items-center gap-2">
            <Building2 className="w-4 h-4 text-amber-400" />
            All practices ({practices.length})
          </CardTitle>
          <div className="relative max-w-xs w-full">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <Input
              data-testid="practices-search"
              placeholder="Search by name, contact email, or ID..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-9 bg-slate-950 border-slate-800 text-slate-100 placeholder:text-slate-600"
            />
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-12 flex justify-center">
              <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />
            </div>
          ) : filtered.length === 0 ? (
            <div className="p-12 text-center text-slate-500 text-sm" data-testid="practices-empty">
              {practices.length === 0
                ? 'No practices yet. Click "Create New Practice" to bootstrap the first clinic.'
                : 'No practices match your search.'}
            </div>
          ) : (
            <div className="divide-y divide-slate-800">
              {filtered.map(p => (
                <div
                  key={p.id}
                  data-testid={`practice-row-${p.id}`}
                  className="px-5 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3 hover:bg-slate-800/40 transition"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-semibold text-slate-100">{p.name || '— unnamed —'}</p>
                      <Badge variant="outline" className={`text-[10px] uppercase tracking-wider border-slate-700 ${
                        p.status === 'active' ? 'text-teal-300' : p.status === 'suspended' ? 'text-red-300' : 'text-amber-300'
                      }`}>{p.status || 'active'}</Badge>
                      <Badge variant="outline" className="text-[10px] uppercase tracking-wider border-violet-500/40 text-violet-300 bg-violet-500/5" data-testid={`plan-badge-${p.id}`}>
                        <Tag className="w-2.5 h-2.5 mr-1" /> {p.subscription_plan || 'basic'}
                      </Badge>
                      {p.billing_status && p.billing_status !== 'active' && (
                        <Badge className={`text-[10px] uppercase tracking-wider border ${
                          p.billing_status === 'past_due'
                            ? 'border-red-500/40 text-red-300 bg-red-500/10'
                            : 'border-amber-500/40 text-amber-300 bg-amber-500/10'
                        } hover:bg-red-500/10`}>{p.billing_status}</Badge>
                      )}
                      {p.retell_provisioned
                        ? <Badge className="bg-teal-500/15 text-teal-300 border border-teal-500/30 hover:bg-teal-500/15">Retell ready</Badge>
                        : <Badge className="bg-amber-500/15 text-amber-300 border border-amber-500/30 hover:bg-amber-500/15">No Retell agent</Badge>}
                    </div>
                    <p className="text-xs text-slate-400 mt-1 truncate">
                      {p.contact_email || 'No contact email'}
                      {p.retell_phone_number && <span className="ml-3 text-slate-500">· {p.retell_phone_number}</span>}
                    </p>
                    <p className="text-[10px] text-slate-600 mt-1 font-mono truncate">{p.id}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      data-testid={`practice-plan-${p.id}`}
                      variant="outline"
                      size="sm"
                      onClick={() => setPlanEditor({
                        practiceId: p.id, practiceName: p.name,
                        currentPlan: p.subscription_plan || 'basic',
                        newPlan: p.subscription_plan || 'basic',
                        reason: '',
                      })}
                      className="border-violet-500/40 bg-violet-500/5 text-violet-200 hover:bg-violet-500/15"
                      title="Change subscription plan"
                    >
                      <Tag className="w-3.5 h-3.5 mr-1" /> Plan
                    </Button>
                    <Button
                      data-testid={`practice-impersonate-${p.id}`}
                      variant="outline"
                      size="sm"
                      disabled={p.status === 'suspended' || impersonatingId === p.id}
                      onClick={() => onImpersonate(p)}
                      className="border-amber-500/40 bg-amber-500/5 text-amber-200 hover:bg-amber-500/15 hover:text-amber-100 disabled:opacity-40"
                      title={p.status === 'suspended' ? 'Activate the practice first' : 'Drop into this clinic\'s UI as its admin'}
                    >
                      {impersonatingId === p.id
                        ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />
                        : <UserCog className="w-3.5 h-3.5 mr-1" />}
                      Impersonate
                    </Button>
                    <Button
                      data-testid={`practice-retell-${p.id}`}
                      variant="outline"
                      size="sm"
                      onClick={() => navigate(`/admin/retell?practice=${p.id}`)}
                      className="border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800"
                    >
                      <Phone className="w-3.5 h-3.5 mr-1" /> Retell
                    </Button>
                    {p.status === 'suspended' ? (
                      <Button
                        data-testid={`practice-activate-${p.id}`}
                        size="sm"
                        onClick={() => setConfirmAction({ practiceId: p.id, type: 'activate', name: p.name })}
                        className="bg-teal-500/20 text-teal-200 hover:bg-teal-500/30 border border-teal-500/40"
                      >
                        <Play className="w-3.5 h-3.5 mr-1" /> Activate
                      </Button>
                    ) : (
                      <Button
                        data-testid={`practice-suspend-${p.id}`}
                        variant="outline"
                        size="sm"
                        onClick={() => setConfirmAction({ practiceId: p.id, type: 'suspend', name: p.name })}
                        className="border-red-500/40 text-red-300 bg-red-500/5 hover:bg-red-500/15 hover:text-red-200"
                      >
                        <Pause className="w-3.5 h-3.5 mr-1" /> Suspend
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create Practice Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-slate-900 border-slate-800 text-slate-100 max-w-lg" data-testid="create-practice-dialog">
          <DialogHeader>
            <DialogTitle className="text-white">Create New Practice</DialogTitle>
            <DialogDescription className="text-slate-400">
              Provisions a new clinic + its first admin user. The admin will land on the onboarding wizard at first login.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <Label className="text-slate-300">Practice name</Label>
              <Input
                data-testid="form-practice-name"
                value={form.practice_name}
                onChange={e => setForm({ ...form, practice_name: e.target.value })}
                placeholder="Riverside Dental Clinic"
                className="bg-slate-950 border-slate-800 text-slate-100"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-slate-300">Contact email</Label>
                <Input
                  data-testid="form-contact-email"
                  type="email"
                  value={form.contact_email}
                  onChange={e => setForm({ ...form, contact_email: e.target.value })}
                  placeholder="hello@clinic.com"
                  className="bg-slate-950 border-slate-800 text-slate-100"
                />
              </div>
              <div>
                <Label className="text-slate-300">Contact phone</Label>
                <Input
                  data-testid="form-contact-phone"
                  value={form.contact_phone}
                  onChange={e => setForm({ ...form, contact_phone: e.target.value })}
                  placeholder="+1 555 555 1234"
                  className="bg-slate-950 border-slate-800 text-slate-100"
                />
              </div>
            </div>

            <div>
              <Label className="text-slate-300">Timezone</Label>
              <Input
                data-testid="form-timezone"
                value={form.timezone}
                onChange={e => setForm({ ...form, timezone: e.target.value })}
                className="bg-slate-950 border-slate-800 text-slate-100"
              />
            </div>

            <div className="border-t border-slate-800 pt-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-amber-400 mb-3">First admin user</p>

              <div className="grid grid-cols-2 gap-3 mb-3">
                <div>
                  <Label className="text-slate-300">Admin name</Label>
                  <Input
                    data-testid="form-admin-name"
                    value={form.admin_full_name}
                    onChange={e => setForm({ ...form, admin_full_name: e.target.value })}
                    placeholder="Dr. Jane Doe"
                    className="bg-slate-950 border-slate-800 text-slate-100"
                  />
                </div>
                <div>
                  <Label className="text-slate-300">Admin email</Label>
                  <Input
                    data-testid="form-admin-email"
                    type="email"
                    value={form.admin_email}
                    onChange={e => setForm({ ...form, admin_email: e.target.value })}
                    placeholder="jane@clinic.com"
                    className="bg-slate-950 border-slate-800 text-slate-100"
                  />
                </div>
              </div>

              <div>
                <Label className="text-slate-300">Temporary password (8+ chars)</Label>
                <Input
                  data-testid="form-admin-password"
                  type="text"
                  value={form.admin_password}
                  onChange={e => setForm({ ...form, admin_password: e.target.value })}
                  placeholder="Send to admin securely"
                  className="bg-slate-950 border-slate-800 text-slate-100 font-mono"
                />
                <p className="text-[10px] text-slate-500 mt-1">They can change it after their first login.</p>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setDialogOpen(false)}
              disabled={submitting}
              className="text-slate-300 hover:bg-slate-800 hover:text-white"
            >Cancel</Button>
            <Button
              data-testid="form-submit"
              onClick={submitCreate}
              disabled={submitting}
              className="bg-gradient-to-r from-red-500 to-amber-500 hover:from-red-400 hover:to-amber-400 text-white border-0"
            >
              {submitting && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
              Create practice
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Plan editor dialog */}
      <Dialog open={!!planEditor} onOpenChange={(open) => !open && setPlanEditor(null)}>
        <DialogContent className="bg-slate-900 border-slate-800 text-slate-100 max-w-lg" data-testid="plan-editor-dialog">
          <DialogHeader>
            <DialogTitle className="text-white">
              Change plan for <span className="text-violet-300">{planEditor?.practiceName}</span>
            </DialogTitle>
            <DialogDescription className="text-slate-400">
              This is a manual override. Stripe is normally the source of truth — use this for comp accounts,
              testing, or to fix data while a Stripe webhook is pending.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            {plans.map(p => {
              const isSelected = planEditor?.newPlan === p.id;
              const isCurrent = planEditor?.currentPlan === p.id;
              return (
                <button
                  key={p.id}
                  data-testid={`plan-option-${p.id}`}
                  onClick={() => setPlanEditor(e => ({ ...e, newPlan: p.id }))}
                  className={`w-full text-left p-3 rounded-lg border transition ${
                    isSelected
                      ? 'border-violet-500/60 bg-violet-500/10'
                      : 'border-slate-800 hover:bg-slate-800/60'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-semibold text-slate-100">
                        {p.name} <span className="text-slate-500 font-normal">${p.price_usd}/mo</span>
                        {isCurrent && <span className="ml-2 text-[10px] uppercase tracking-wider text-teal-300">current</span>}
                      </p>
                      <p className="text-xs text-slate-400 mt-1">{p.description}</p>
                    </div>
                    <div className="text-right text-[10px] text-slate-500 shrink-0 ml-3">
                      <p>{p.calls_included} calls</p>
                      <p>{p.providers_max} providers</p>
                      <p>{p.locations_max} locations</p>
                    </div>
                  </div>
                  {isSelected && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {Object.entries(p.features || {}).filter(([, v]) => v).map(([k]) => (
                        <span key={k} className="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-200 border border-violet-500/30">
                          {k}
                        </span>
                      ))}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
          <div>
            <Label className="text-slate-300 text-xs">Reason (logged for audit)</Label>
            <Input
              data-testid="plan-reason-input"
              value={planEditor?.reason || ''}
              onChange={e => setPlanEditor(p => ({ ...p, reason: e.target.value }))}
              placeholder="e.g. comp account for design partner"
              className="bg-slate-950 border-slate-800 text-slate-100 mt-1"
            />
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => setPlanEditor(null)}
              disabled={savingPlan}
              className="text-slate-300 hover:bg-slate-800 hover:text-white"
            >Cancel</Button>
            <Button
              data-testid="plan-save"
              onClick={savePlan}
              disabled={savingPlan || planEditor?.newPlan === planEditor?.currentPlan}
              className="bg-violet-500 hover:bg-violet-400 text-white"
            >
              {savingPlan && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
              Apply plan change
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Suspend / Activate confirmation */}
      <AlertDialog open={!!confirmAction} onOpenChange={open => !open && setConfirmAction(null)}>
        <AlertDialogContent className="bg-slate-900 border-slate-800 text-slate-100" data-testid="confirm-status-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-white">
              {confirmAction?.type === 'suspend' ? 'Suspend' : 'Activate'} <span className="text-amber-300">{confirmAction?.name}</span>?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-slate-400">
              {confirmAction?.type === 'suspend'
                ? 'All practice users will be locked out immediately. Their data is preserved and can be restored by activating the practice.'
                : 'All practice users will regain access. The clinic will resume normal operation.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-slate-800 border-slate-700 text-slate-200 hover:bg-slate-700 hover:text-white">Cancel</AlertDialogCancel>
            <AlertDialogAction
              data-testid="confirm-status-action"
              onClick={runSuspendOrActivate}
              className={confirmAction?.type === 'suspend'
                ? 'bg-red-500 hover:bg-red-400 text-white'
                : 'bg-teal-500 hover:bg-teal-400 text-white'}
            >
              {confirmAction?.type === 'suspend' ? 'Suspend practice' : 'Activate practice'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
