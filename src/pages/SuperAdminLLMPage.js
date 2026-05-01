import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Cpu, RefreshCw, Loader2, Zap, TrendingUp, ShieldCheck, Clock, AlertTriangle,
  Sparkles,
} from 'lucide-react';
import { toast } from 'sonner';

function StatTile({ icon: Icon, label, value, sublabel, accent = 'amber' }) {
  const colors = {
    amber: 'border-amber-500/20 from-amber-500/10 text-amber-300',
    teal: 'border-teal-500/20 from-teal-500/10 text-teal-300',
    violet: 'border-violet-500/20 from-violet-500/10 text-violet-300',
    red: 'border-red-500/20 from-red-500/10 text-red-300',
  };
  return (
    <div className={`rounded-xl border bg-gradient-to-br to-transparent ${colors[accent]} p-5`}>
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

export default function SuperAdminLLMPage() {
  const { axiosAuth } = useAuth();
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [providers, setProviders] = useState([]);
  const [days, setDays] = useState(7);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [a, b, c] = await Promise.all([
        axiosAuth().get(`/llm/stats?days=${days}`),
        axiosAuth().get('/llm/logs?limit=25'),
        axiosAuth().get('/llm/providers'),
      ]);
      setStats(a.data);
      setLogs(b.data.logs || []);
      setProviders(c.data.providers || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to load LLM stats');
    } finally {
      setLoading(false);
    }
  }, [axiosAuth, days]);

  useEffect(() => { load(); }, [load]);

  const t = stats?.totals || {};
  const cost = stats?.cost || {};
  const escalationRate = ((t.escalation_rate ?? 0) * 100).toFixed(1);
  const cheapTurns = (t.turns ?? 0) - (t.escalated_turns ?? 0);
  const cacheStats = stats?.cache || {};

  const fmtUsd = (n) => {
    const v = Number(n) || 0;
    if (v < 0.01 && v > 0) return `$${v.toFixed(6)}`;
    if (v < 1) return `$${v.toFixed(4)}`;
    return `$${v.toFixed(2)}`;
  };
  const savingsPct = ((cost.savings_pct ?? 0) * 100).toFixed(1);

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto" data-testid="superadmin-llm">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-6">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-amber-400">Platform Operations</p>
          <h1 className="text-3xl font-bold text-white mt-1 flex items-center gap-2">
            <Cpu className="w-7 h-7 text-amber-400" /> LLM Routing
          </h1>
          <p className="text-sm text-slate-400 mt-2 max-w-2xl">
            Cost-aware routing across providers. Cheap models handle most turns; we escalate
            only when conversations require it.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={e => setDays(parseInt(e.target.value))}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-slate-200"
            data-testid="llm-window-select"
          >
            <option value={1}>Last 24h</option>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
          </select>
          <Button
            variant="outline"
            size="sm"
            onClick={load}
            disabled={loading}
            className="border-slate-700 bg-slate-900 text-slate-200 hover:bg-slate-800 hover:text-white"
            data-testid="llm-refresh"
          >
            <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
          </Button>
        </div>
      </div>

      {/* Provider availability banner */}
      {providers.length === 1 && providers[0] === 'stub' && (
        <div className="mb-6 flex items-start gap-3 p-4 rounded-lg bg-amber-500/5 border border-amber-500/20" data-testid="llm-no-keys-banner">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-semibold text-amber-200">No real LLM provider configured</p>
            <p className="text-slate-400 mt-1">
              Routing layer is wired and the stub provider is responding for tests. To go live,
              set <code className="px-1 py-0.5 bg-slate-800 rounded text-amber-300">OPENAI_API_KEY</code>,{' '}
              <code className="px-1 py-0.5 bg-slate-800 rounded text-amber-300">ANTHROPIC_API_KEY</code>, or{' '}
              <code className="px-1 py-0.5 bg-slate-800 rounded text-amber-300">GOOGLE_API_KEY</code> in <code className="px-1 py-0.5 bg-slate-800 rounded text-amber-300">backend/.env</code>.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatTile icon={Zap} label="Total turns" value={t.turns ?? 0} sublabel={`${days}-day window`} accent="amber" />
        <StatTile icon={ShieldCheck} label="Cheap-model turns" value={cheapTurns} sublabel={`${(100 - parseFloat(escalationRate)).toFixed(1)}% of all turns`} accent="teal" />
        <StatTile icon={TrendingUp} label="Escalations" value={t.escalated_turns ?? 0} sublabel={`${escalationRate}% escalation rate`} accent="violet" />
        <StatTile icon={Clock} label="Total tokens" value={(t.total_tokens ?? 0).toLocaleString()} sublabel={`in ${(t.input_tokens ?? 0).toLocaleString()} · out ${(t.output_tokens ?? 0).toLocaleString()}`} accent="red" />
      </div>

      {/* ── Cost Savings ROI hero ───────────────────────────────────── */}
      <div
        data-testid="llm-cost-savings"
        className="relative overflow-hidden rounded-2xl border border-emerald-500/25 bg-gradient-to-br from-emerald-500/10 via-emerald-500/5 to-transparent p-6 mb-6"
      >
        <div className="absolute -top-12 -right-12 w-48 h-48 rounded-full bg-emerald-500/10 blur-3xl" />
        <div className="relative flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <Sparkles className="w-4 h-4 text-emerald-300" />
              <p className="text-[11px] font-bold uppercase tracking-widest text-emerald-300">Cost Savings ROI</p>
            </div>
            <p className="text-5xl lg:text-6xl font-bold text-white tabular-nums" data-testid="llm-savings-usd">
              {fmtUsd(cost.savings_usd ?? 0)}
            </p>
            <p className="text-sm text-slate-300 mt-2 max-w-xl">
              <span className="text-emerald-300 font-semibold">{savingsPct}%</span> saved over a baseline of routing
              every turn through{' '}
              <code className="bg-slate-900/60 border border-slate-700 px-1.5 py-0.5 rounded text-amber-300 text-xs">
                {cost.baseline_provider}·{cost.baseline_model}
              </code>{' '}
              ({fmtUsd(cost.baseline_input_per_million ?? 0)}/M in · {fmtUsd(cost.baseline_output_per_million ?? 0)}/M out).
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 shrink-0 min-w-[280px]">
            <div className="bg-slate-950/60 border border-slate-800 rounded-lg px-4 py-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">Actual spend</p>
              <p className="text-lg font-bold text-slate-100 tabular-nums mt-1" data-testid="llm-actual-usd">
                {fmtUsd(cost.actual_usd ?? 0)}
              </p>
            </div>
            <div className="bg-slate-950/60 border border-slate-800 rounded-lg px-4 py-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">If all-escalated</p>
              <p className="text-lg font-bold text-slate-100 tabular-nums mt-1" data-testid="llm-baseline-usd">
                {fmtUsd(cost.if_all_escalated_usd ?? 0)}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <Card className="bg-slate-900 border-slate-800">
          <CardHeader className="border-b border-slate-800">
            <CardTitle className="text-base text-slate-100">By model</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {(stats?.by_model?.length ?? 0) === 0 ? (
              <p className="p-8 text-sm text-slate-500 text-center" data-testid="llm-by-model-empty">No turns recorded yet.</p>
            ) : (
              <div className="divide-y divide-slate-800">
                {stats.by_model.map((row, i) => (
                  <div key={i} className="px-5 py-3 flex items-center justify-between">
                    <div className="min-w-0">
                      <p className="text-sm font-mono text-slate-100 truncate">
                        <span className="text-amber-300">{row.provider}</span> · {row.model}
                      </p>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        {row.calls} turns · in {row.input_tokens.toLocaleString()} · out {row.output_tokens.toLocaleString()} · {row.avg_latency_ms.toFixed(0)}ms avg · <span className="text-emerald-300 font-semibold">{fmtUsd(row.cost_usd)}</span>
                      </p>
                    </div>
                    {row.escalated
                      ? <Badge className="bg-violet-500/15 text-violet-300 border border-violet-500/30 hover:bg-violet-500/15">Escalated</Badge>
                      : <Badge className="bg-teal-500/15 text-teal-300 border border-teal-500/30 hover:bg-teal-500/15">Default</Badge>}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="bg-slate-900 border-slate-800">
          <CardHeader className="border-b border-slate-800">
            <CardTitle className="text-base text-slate-100">Top escalation triggers</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {(stats?.top_triggers?.length ?? 0) === 0 ? (
              <p className="p-8 text-sm text-slate-500 text-center">No escalations yet.</p>
            ) : (
              <div className="divide-y divide-slate-800">
                {stats.top_triggers.map((t, i) => (
                  <div key={i} className="px-5 py-3 flex items-center justify-between">
                    <span className="text-sm font-mono text-amber-300">{t.trigger || '—'}</span>
                    <Badge variant="outline" className="border-slate-700 text-slate-300">{t.count}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="bg-slate-900 border-slate-800 mb-6">
        <CardHeader className="border-b border-slate-800">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base text-slate-100">Cache</CardTitle>
            <span className="text-xs text-slate-500">In-process per-call cache (call_id keyed)</span>
          </div>
        </CardHeader>
        <CardContent className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-4">
          {[
            ['Hits', cacheStats.hits ?? 0],
            ['Misses', cacheStats.misses ?? 0],
            ['Hit rate', `${((cacheStats.hit_rate ?? 0) * 100).toFixed(1)}%`],
            ['Active calls', cacheStats.active_calls ?? 0],
            ['Evictions', cacheStats.evictions ?? 0],
          ].map(([k, v]) => (
            <div key={k} className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">{k}</p>
              <p className="text-base font-bold text-slate-100 mt-0.5 tabular-nums">{v}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className="bg-slate-900 border-slate-800">
        <CardHeader className="border-b border-slate-800">
          <CardTitle className="text-base text-slate-100">Recent routing decisions</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {logs.length === 0 ? (
            <p className="p-8 text-sm text-slate-500 text-center">No log entries yet.</p>
          ) : (
            <div className="divide-y divide-slate-800 max-h-[420px] overflow-y-auto">
              {logs.map(l => (
                <div key={l.id} className="px-5 py-2.5 flex items-center justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-mono text-slate-200 truncate">
                      <span className="text-amber-300">{l.provider}</span>·{l.model}
                      {l.escalated && <span className="text-violet-300 ml-2">↑ {l.trigger}</span>}
                      {l.error && <span className="text-red-300 ml-2">! err</span>}
                    </p>
                    <p className="text-[10px] text-slate-500 truncate">
                      {new Date(l.timestamp).toLocaleString()} · in {l.input_tokens} · out {l.output_tokens} · {l.latency_ms}ms
                      {l.call_id && <span className="ml-2">call={l.call_id}</span>}
                    </p>
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
