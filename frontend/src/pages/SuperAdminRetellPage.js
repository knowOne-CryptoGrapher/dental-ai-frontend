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
import { Copy, Check, Phone, Sparkles, RefreshCw } from 'lucide-react';

// Per-function Retell node config. Keys must match the backend's
// _function_urls() dict in superadmin_router.py exactly.
const FUNCTION_NODE_META = {
  lookup_patient:              { argsOnlyOff: true },
  list_providers:              {},
  check_provider_availability: {},
  book_appointment:            { argsOnlyOff: true },
  get_patient_appointments:    { argsOnlyOff: true },
  cancel_appointment:          { argsOnlyOff: true },
  register_patient:            { argsOnlyOff: true },
  get_practice_context:        { header: 'x-retell-api-key' },
  query_knowledge_base:        { header: 'x-retell-api-key' },
  ingest_call_summary:         { header: 'x-retell-secret' },
};

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
                  <CardTitle className="text-base text-slate-100">How to Provision a New Practice</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 pt-4 text-sm">
                  <div>
                    <p className="font-semibold text-amber-300">Step 1 — Copy the system prompt</p>
                    <p className="text-slate-400 mt-0.5">Click "Copy prompt" below and paste it into the Retell Dashboard when creating the agent.</p>
                  </div>
                  <div>
                    <p className="font-semibold text-amber-300">Step 2 — Create the agent in Retell</p>
                    <p className="text-slate-400 mt-0.5">Go to Retell Dashboard → Agents → Create Agent → Single Prompt Agent. Paste the copied prompt. Set the voice to your preferred option.</p>
                  </div>
                  <div>
                    <p className="font-semibold text-amber-300">Step 3 — Add the 10 function nodes</p>
                    <p className="text-slate-400 mt-0.5">
                      In the agent's Functions tab, add each function listed below using the URLs shown.
                      Set "Payload: args only" ON for every function except the ones marked "Args Only OFF" in the list below.
                      Add the custom header shown next to a function, where one is listed.
                    </p>
                  </div>
                  <div>
                    <p className="font-semibold text-amber-300">Step 4 — Set the webhook URL</p>
                    <p className="text-slate-400 mt-0.5">Go to Retell Dashboard → Settings → Webhooks. Paste the webhook URL shown below.</p>
                  </div>
                  <div>
                    <p className="font-semibold text-amber-300">Step 5 — Save the agent ID here</p>
                    <p className="text-slate-400 mt-0.5">Copy the Agent ID from Retell Dashboard → Agents → your agent → ID. Paste it into the Agent ID field below and click Save.</p>
                  </div>
                  <div>
                    <p className="font-semibold text-amber-300">Step 6 — Test</p>
                    <p className="text-slate-400 mt-0.5">Make a test call to verify the agent responds correctly. Check the Call Logs page in the practice dashboard after the call.</p>
                  </div>
                </CardContent>
              </Card>

              <Card className={cardCls}>
                <CardHeader className="border-b border-slate-800">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-slate-100">{retellCfg.practice_name}</CardTitle>
                      <p className="text-xs text-slate-500 mt-1">practice_id: <code className="text-amber-300">{retellCfg.practice_id}</code></p>
                    </div>
                    <Badge className="bg-amber-500/15 text-amber-300 border border-amber-500/30 hover:bg-amber-500/15">Manual setup required</Badge>
                  </div>
                </CardHeader>
              </Card>

              <Card className={cardCls}>
                <CardHeader className="border-b border-slate-800">
                  <CardTitle className="text-base text-slate-100">Saved Retell Identity</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 pt-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <Label className="text-slate-300">Retell Agent ID (from Retell Dashboard → Agents → your agent → ID)</Label>
                      <Input data-testid="agent-id-input" value={agentId} onChange={e => setAgentId(e.target.value)} placeholder="agent_xxxxxxxxxxxxxxxxxxxxxxxx" className={inputCls} />
                    </div>
                    <div>
                      <Label className="text-slate-300">Assigned phone number (E.164 format)</Label>
                      <Input data-testid="phone-input" value={phone} onChange={e => setPhone(e.target.value)} placeholder="+16041234567" className={inputCls} />
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
                      {Object.entries(retellCfg.function_urls).map(([name, url]) => {
                        const meta = FUNCTION_NODE_META[name] || {};
                        return (
                          <div key={name} className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs space-y-1">
                            <div className="flex items-center gap-2">
                              <code className="flex-1 truncate text-slate-300"><strong className="text-amber-300">{name}</strong> → {url}</code>
                              <CopyBtn text={url} label="" />
                            </div>
                            {(meta.header || meta.argsOnlyOff) && (
                              <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-500">
                                {meta.header && (
                                  <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">Header: <code className="text-amber-300">{meta.header}</code></span>
                                )}
                                {meta.argsOnlyOff && (
                                  <span className="px-1.5 py-0.5 rounded bg-red-500/10 text-red-300 border border-red-500/20">Payload: Args Only OFF</span>
                                )}
                              </div>
                            )}
                          </div>
                        );
                      })}
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
