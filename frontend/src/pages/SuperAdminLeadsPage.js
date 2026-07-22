import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../components/ui/alert-dialog';
import { toast } from 'sonner';
import { Loader2, RefreshCw, Inbox, Check, X, Tag, Phone, MapPin } from 'lucide-react';

const TABS = [
  { key: 'all', label: 'All' },
  { key: 'new', label: 'New' },
  { key: 'approved', label: 'Approved' },
  { key: 'denied', label: 'Denied' },
];

export default function SuperAdminLeadsPage() {
  const { axiosAuth } = useAuth();

  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('all');
  const [confirmAction, setConfirmAction] = useState(null); // { leadId, type: 'approve'|'deny', name }
  const [actingId, setActingId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = tab === 'all' ? {} : { status: tab };
      const r = await axiosAuth().get('/superadmin/leads', { params });
      setLeads(r.data.leads || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load leads');
    } finally {
      setLoading(false);
    }
  }, [axiosAuth, tab]);

  useEffect(() => { load(); }, [load]);

  const runAction = async () => {
    if (!confirmAction) return;
    const { leadId, type } = confirmAction;
    setActingId(leadId);
    try {
      await axiosAuth().post(`/superadmin/leads/${leadId}/${type}`);
      toast.success(type === 'approve' ? 'Lead approved — invite sent' : 'Lead denied');
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Action failed');
    } finally {
      setActingId(null);
      setConfirmAction(null);
    }
  };

  const statusBadge = (status) => {
    if (status === 'approved') {
      return <Badge className="bg-teal-500/15 text-teal-300 border border-teal-500/30 hover:bg-teal-500/15">Approved</Badge>;
    }
    if (status === 'denied') {
      return <Badge className="bg-red-500/15 text-red-300 border border-red-500/30 hover:bg-red-500/15">Denied</Badge>;
    }
    return <Badge variant="outline" className="text-[10px] uppercase tracking-wider border-amber-500/40 text-amber-300">New</Badge>;
  };

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto" data-testid="superadmin-leads">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-6">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-amber-400">Platform Operations</p>
          <h1 className="text-3xl font-bold text-white mt-1">Lead Approvals</h1>
          <p className="text-sm text-slate-400 mt-2 max-w-2xl">
            Enterprise and Elite leads from the Contact Sales form. Approve to provision a practice and email
            the lead an invite to set their own password; deny to send a polite rejection.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={load}
          disabled={loading}
          className="border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800 hover:text-white"
          data-testid="leads-refresh-btn"
        >
          <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </Button>
      </div>

      <div className="flex gap-1.5 mb-4">
        {TABS.map(t => (
          <button
            key={t.key}
            data-testid={`leads-tab-${t.key}`}
            onClick={() => setTab(t.key)}
            className={`px-3 py-1.5 rounded-lg text-[13px] font-medium transition-all ${
              tab === t.key
                ? 'bg-gradient-to-r from-red-500/15 to-amber-500/10 text-amber-200 border border-amber-500/30'
                : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100 border border-transparent'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <Card className="bg-slate-900 border-slate-800">
        <CardHeader className="border-b border-slate-800">
          <CardTitle className="text-slate-100 text-base flex items-center gap-2">
            <Inbox className="w-4 h-4 text-amber-400" />
            {TABS.find(t => t.key === tab)?.label} leads ({leads.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-12 flex justify-center">
              <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />
            </div>
          ) : leads.length === 0 ? (
            <div className="p-12 text-center text-slate-500 text-sm" data-testid="leads-empty">
              No leads in this view.
            </div>
          ) : (
            <div className="divide-y divide-slate-800">
              {leads.map(l => (
                <div
                  key={l.id}
                  data-testid={`lead-row-${l.id}`}
                  className="px-5 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3 hover:bg-slate-800/40 transition"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-semibold text-slate-100">{l.name}</p>
                      {statusBadge(l.status)}
                      <Badge variant="outline" className="text-[10px] uppercase tracking-wider border-violet-500/40 text-violet-300 bg-violet-500/5">
                        <Tag className="w-2.5 h-2.5 mr-1" /> {l.requested_plan}
                      </Badge>
                      <Badge variant="outline" className="text-[10px] uppercase tracking-wider border-slate-700 text-slate-300">
                        {l.clinic_size} locations
                      </Badge>
                    </div>
                    <p className="text-xs text-slate-400 mt-1 truncate">
                      {l.email}
                      {l.phone && <span className="ml-3 inline-flex items-center gap-1 text-slate-500"><Phone className="w-3 h-3" /> {l.phone}</span>}
                      {(l.province || l.country) && (
                        <span className="ml-3 inline-flex items-center gap-1 text-slate-500">
                          <MapPin className="w-3 h-3" /> {[l.province, l.country].filter(Boolean).join(', ')}
                        </span>
                      )}
                    </p>
                    {l.message && <p className="text-xs text-slate-500 mt-1 italic truncate">"{l.message}"</p>}
                    <p className="text-[10px] text-slate-600 mt-1">
                      Submitted {l.created_at ? new Date(l.created_at).toLocaleString() : 'unknown'}
                      {l.status === 'approved' && l.practice_id && (
                        <span className="ml-3 font-mono">practice: {l.practice_id}</span>
                      )}
                    </p>
                  </div>
                  {l.status === 'new' && (
                    <div className="flex items-center gap-2 shrink-0">
                      <Button
                        data-testid={`lead-approve-${l.id}`}
                        size="sm"
                        disabled={actingId === l.id}
                        onClick={() => setConfirmAction({ leadId: l.id, type: 'approve', name: l.name })}
                        className="bg-teal-500/20 text-teal-200 hover:bg-teal-500/30 border border-teal-500/40"
                      >
                        <Check className="w-3.5 h-3.5 mr-1" /> Approve
                      </Button>
                      <Button
                        data-testid={`lead-deny-${l.id}`}
                        variant="outline"
                        size="sm"
                        disabled={actingId === l.id}
                        onClick={() => setConfirmAction({ leadId: l.id, type: 'deny', name: l.name })}
                        className="border-red-500/40 text-red-300 bg-red-500/5 hover:bg-red-500/15 hover:text-red-200"
                      >
                        <X className="w-3.5 h-3.5 mr-1" /> Deny
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <AlertDialog open={!!confirmAction} onOpenChange={open => !open && setConfirmAction(null)}>
        <AlertDialogContent className="bg-slate-900 border-slate-800 text-slate-100" data-testid="lead-confirm-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-white">
              {confirmAction?.type === 'approve' ? 'Approve' : 'Deny'} <span className="text-amber-300">{confirmAction?.name}</span>?
            </AlertDialogTitle>
            <AlertDialogDescription className="text-slate-400">
              {confirmAction?.type === 'approve'
                ? 'This will create their practice and send them an invite email.'
                : 'This will send them a rejection email.'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="bg-slate-800 border-slate-700 text-slate-200 hover:bg-slate-700 hover:text-white">Cancel</AlertDialogCancel>
            <AlertDialogAction
              data-testid="lead-confirm-action"
              onClick={runAction}
              className={confirmAction?.type === 'approve'
                ? 'bg-teal-500 hover:bg-teal-400 text-white'
                : 'bg-red-500 hover:bg-red-400 text-white'}
            >
              {confirmAction?.type === 'approve' ? 'Approve lead' : 'Deny lead'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
