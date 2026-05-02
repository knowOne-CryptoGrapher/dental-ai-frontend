import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import { Loader2, Copy, Check, Phone, Sparkles, RefreshCw } from 'lucide-react';

function CopyBtn({ text, label = 'Copy' }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="outline"
      size="sm"
      className="border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800 hover:text-white"
      onClick={async () => {
        try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1200); }
        catch { toast.error('Copy failed'); }
      }}
    >
      {copied ? <Check className="w-4 h-4 mr-1" /> : <Copy className="w-4 h-4 mr-1" />}
      {copied ? 'Copied' : label}
    </Button>
  );
}

export default function SuperAdminRetellPage() {
  const { axiosAuth } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const [practices, setPractices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [retellCfg, setRetellCfg] = useState(null);
  const [agentId, setAgentId] = useState('');
  const [phone, setPhone] = useState('');
  const [busy, setBusy] = useState(false);
  const [automationStatus, setAutomationStatus] = useState(null);

  const loadPractices = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axiosAuth().get('/superadmin/practices');
      setPractices(r.data.practices || []);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to load practices'); }
    finally { setLoading(false); }
  }, [axiosAuth]);

  const loadPracticeRetell = useCallback(async (practiceId) => {
    setSelected(practiceId);
    setRetellCfg(null);
    try {
      const r = await axiosAuth().get(`/superadmin/practices/${practiceId}/retell`);
      setRetellCfg(r.data);
      setAgentId(r.data.agent_id || '');
      setPhone(r.data.phone_number || '');
      setAutomationStatus(r.data.automation_available ? 'available' : 'manual');
    } catch (e) { toast.error('Failed to load practice Retell config'); }
  }, [axiosAuth]);

  useEffect(() => { loadPractices(); }, [loadPractices]);

  // Deep-link support: /admin/retell?practice=<id>
  useEffect(() => {
    const pid = searchParams.get('practice');
    if (pid && pid !== selected) {
      loadPracticeRetell(pid);
    }
  }, [searchParams, selected, loadPracticeRetell]);

  const onSelectPractice = (pid) => {
    loadPracticeRetell(pid);
    setSearchParams({ practice: pid }, { replace: true });
  };

  const saveManual = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await axiosAuth().put(`/superadmin/practices/${selected}/retell`, {
        agent_id: agentId || null, phone_number: phone || null,
      });
      toast.success('Saved');
      await loadPractices();
      await loadPracticeRetell(selected);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setBusy(false); }
  };

  const provision = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await axiosAuth().post(`/superadmin/practices/${selected}/retell/provision`);
      toast.success('Agent provisioned');
      await loadPracticeRetell(selected);
    } catch (e) {
      const detail = e.response?.data?.detail || 'Provision failed';
      if (e.response?.status === 501) toast.warning(detail, { duration: 6000 });
      else toast.error(detail);
    } finally { setBusy(false); }
  };

  const resync = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await axiosAuth().post(`/superadmin/practices/${selected}/retell/resync`);
      toast.success('Re-synced');
    } catch (e) {
      const detail = e.response?.data?.detail || 'Re-sync failed';
      if (e.response?.status === 501) toast.warning(detail, { duration: 6000 });
      else toast.error(detail);
    } finally { setBusy(false); }
  };

  const cardCls = "bg-slate-900 border-slate-800 text-slate-100";
  const inputCls = "bg-slate-950 border-slate-800 text-slate-100 placeholder:text-slate-600";

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto" data-testid="superadmin-retell-page">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-6">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-amber-400">Platform Operations</p>
          <h1 className="text-3xl font-bold text-white mt-1 flex items-center gap-2">
            <Phone className="w-7 h-7 text-amber-400" /> Retell Provisioning
          </h1>
          <p className="text-sm text-slate-400 mt-2 max-w-2xl">
            Provision and manage every clinic's AI receptionist. Pick a practice, then provision its agent or re-sync its prompt.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={loadPractices}
          disabled={loading}
          className="border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800 hover:text-white"
        >
          <RefreshCw className={`w-4 h-4 mr-1 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: practices list */}
        <div className="lg:col-span-4 space-y-2">
          <Card className={cardCls}>
            <CardHeader className="border-b border-slate-800">
              <CardTitle className="text-base text-slate-100">All Practices ({practices.length})</CardTitle>
            </CardHeader>
            <CardContent className="p-3 space-y-1.5 max-h-[70vh] overflow-y-auto">
              {practices.map(p => (
                <button
                  key={p.id}
                  data-testid={`practice-row-${p.id}`}
                  onClick={() => onSelectPractice(p.id)}
                  className={`w-full text-left p-3 rounded-lg border transition ${
                    selected === p.id
                      ? 'border-amber-500/40 bg-amber-500/10'
                      : 'border-slate-800 hover:bg-slate-800/60 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-slate-100 truncate">{p.name}</div>
                      <div className="text-xs text-slate-500 truncate">{p.contact_email}</div>
                    </div>
                    {p.retell_provisioned
                      ? <Badge className="bg-teal-500/15 text-teal-300 border border-teal-500/30 hover:bg-teal-500/15">Provisioned</Badge>
                      : <Badge className="bg-amber-500/15 text-amber-300 border border-amber-500/30 hover:bg-amber-500/15">Needs setup</Badge>}
                  </div>
                </button>
              ))}
              {!practices.length && !loading && <p className="text-sm text-slate-500 px-2 py-3">No practices yet.</p>}
            </CardContent>
          </Card>
        </div>

        {/* Right: Retell config detail */}
        <div className="lg:col-span-8 space-y-4">
          {!selected && (
            <Card className={cardCls}>
              <CardContent className="py-12 text-center text-slate-500">
                <Sparkles className="w-8 h-8 mx-auto text-slate-600" />
                <p className="mt-3 text-sm">Select a practice from the left to manage its Retell setup.</p>
              </CardContent>
            </Card>
          )}

          {selected && retellCfg && (
            <>
              <Card className={cardCls}>
                <CardHeader className="border-b border-slate-800">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-slate-100">{retellCfg.practice_name}</CardTitle>
                      <p className="text-xs text-slate-500 mt-1">practice_id: <code className="text-amber-300">{retellCfg.practice_id}</code></p>
                    </div>
                    {automationStatus === 'available'
                      ? <Badge className="bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/15">Automation ready</Badge>
                      : <Badge className="bg-amber-500/15 text-amber-300 border border-amber-500/30 hover:bg-amber-500/15">Manual mode</Badge>}
                  </div>
                </CardHeader>
                <CardContent className="space-y-3 pt-4">
                  <div className="flex flex-wrap gap-2">
                    <Button
                      data-testid="provision-btn"
                      onClick={provision}
                      disabled={busy}
                      className="bg-gradient-to-r from-red-500 to-amber-500 hover:from-red-400 hover:to-amber-400 text-white border-0"
                    >
                      {busy && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Provision Agent
                    </Button>
                    <Button
                      data-testid="resync-btn"
                      onClick={resync}
                      disabled={busy}
                      variant="outline"
                      className="border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800 hover:text-white"
                    >
                      <RefreshCw className="w-4 h-4 mr-1" /> Re-sync prompt + functions
                    </Button>
                  </div>
                  {automationStatus === 'manual' && (
                    <p className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 p-2.5 rounded-lg">
                      Automation requires <code className="px-1 py-0.5 bg-slate-800 rounded">RETELL_API_KEY</code> in backend env. Use the manual setup section below until it's configured.
                    </p>
                  )}
                </CardContent>
              </Card>

              <Card className={cardCls}>
                <CardHeader className="border-b border-slate-800">
                  <CardTitle className="text-base text-slate-100">Saved Retell Identity</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 pt-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <Label className="text-slate-300">Agent ID</Label>
                      <Input data-testid="agent-id-input" value={agentId} onChange={e => setAgentId(e.target.value)} placeholder="agent_xxxx" className={inputCls} />
                    </div>
                    <div>
                      <Label className="text-slate-300">Phone number</Label>
                      <Input data-testid="phone-input" value={phone} onChange={e => setPhone(e.target.value)} placeholder="+15551112222" className={inputCls} />
                    </div>
                  </div>
                  <Button
                    data-testid="save-manual-btn"
                    onClick={saveManual}
                    disabled={busy}
                    variant="outline"
                    className="border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800 hover:text-white"
                  >Save</Button>
                </CardContent>
              </Card>

              <Card className={cardCls}>
                <CardHeader className="border-b border-slate-800">
                  <CardTitle className="text-base text-slate-100">Manual Setup Reference</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 pt-4">
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <Label className="text-slate-300">Webhook URL</Label>
                      <CopyBtn text={retellCfg.webhook_url} />
                    </div>
                    <code className="block bg-slate-950 border border-slate-800 px-3 py-2 rounded-lg text-xs text-amber-300 break-all">{retellCfg.webhook_url}</code>
                  </div>

                  <div>
                    <Label className="text-slate-300">Function URLs</Label>
                    <div className="space-y-1.5 mt-1">
                      {Object.entries(retellCfg.function_urls).map(([name, url]) => (
                        <div key={name} className="flex items-center gap-2 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs">
                          <code className="flex-1 truncate text-slate-300"><strong className="text-amber-300">{name}</strong> → {url}</code>
                          <CopyBtn text={url} label="" />
                        </div>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <Label className="text-slate-300">Rendered system prompt</Label>
                      <div className="flex gap-2">
                        <span className="text-xs text-slate-500 self-center">hash: <code className="text-amber-300">{retellCfg.prompt_hash}</code></span>
                        <CopyBtn text={retellCfg.rendered_prompt} label="Copy prompt" />
                      </div>
                    </div>
                    <Textarea
                      data-testid="prompt-preview"
                      rows={14}
                      readOnly
                      value={retellCfg.rendered_prompt}
                      className="bg-slate-950 border-slate-800 text-slate-200 font-mono text-xs"
                    />
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
