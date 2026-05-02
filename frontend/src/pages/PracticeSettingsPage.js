import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Textarea } from '../components/ui/textarea';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { toast } from 'sonner';
import { Loader2, Copy, Check } from 'lucide-react';
import ErrorBoundary from '../components/ErrorBoundary';

const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const DAY_LABELS = { mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri', sat: 'Sat', sun: 'Sun' };

function CopyInline({ text }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button variant="ghost" size="sm" onClick={async () => {
      try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1200); }
      catch { toast.error('Copy failed'); }
    }}>
      {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
    </Button>
  );
}

export default function PracticeSettingsPage() {
  const { user, practice, axiosAuth, refreshPractice, isSuperAdmin } = useAuth();
  const pid = user?.practice_id;

  const [branding, setBranding] = useState(null);
  const [hours, setHours] = useState(null);
  const [emergency, setEmergency] = useState(null);
  const [types, setTypes] = useState([]);
  const [newType, setNewType] = useState({ id: '', name: '', duration_min: 30 });
  const [retell, setRetell] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [saving, setSaving] = useState(false);

  const hydrate = useCallback(() => {
    if (practice?.settings) {
      const s = practice.settings;
      setBranding(s.branding || { agent_name: 'Amanda', voice_tone: 'warm_professional', greeting: '', closing: '' });
      // Defensive: handle legacy practices where hours.weekly is missing/empty
      const hoursDoc = s.hours || {};
      setHours({
        ...hoursDoc,
        weekly: hoursDoc.weekly || {
          mon: { open: '08:00', close: '17:00' },
          tue: { open: '08:00', close: '17:00' },
          wed: { open: '08:00', close: '17:00' },
          thu: { open: '08:00', close: '17:00' },
          fri: { open: '08:00', close: '17:00' },
          sat: null,
          sun: null,
        },
      });
      setEmergency(s.emergency || { triggers: [], response_policy: 'earliest_available', after_hours_handoff_phone: '' });
      setTypes(s.appointment_types || []);
      setRetell(s.retell || { agent_id: '', phone_number: '' });
    }
  }, [practice]);

  useEffect(() => { hydrate(); }, [hydrate]);

  const put = async (path, body) => axiosAuth().put(path, body);
  const post = async (path, body) => axiosAuth().post(path, body);
  const del = async (path) => axiosAuth().delete(path);

  const save = async (path, body, label) => {
    setSaving(true);
    try { await put(path, body); toast.success(`${label} saved`); await refreshPractice(); }
    catch (e) { toast.error(e.response?.data?.detail || `Failed to save ${label}`); }
    finally { setSaving(false); }
  };

  const regeneratePrompt = async () => {
    try { const r = await axiosAuth().get(`/agent/${pid}/prompt`); setPrompt(r.data.prompt); }
    catch { toast.error('Failed to render prompt'); }
  };

  if (!practice || !branding) {
    return <div className="p-8 flex justify-center"><Loader2 className="w-6 h-6 animate-spin" /></div>;
  }

  return (
    <div className="p-6 max-w-5xl mx-auto" data-testid="practice-settings-page">
      <h1 className="text-2xl font-bold mb-1">Practice Settings</h1>
      <p className="text-sm text-slate-500 mb-6">Configure {practice.name}. Changes take effect on the next call.</p>

      <Tabs defaultValue="branding" className="space-y-4">
        <TabsList>
          <TabsTrigger value="branding" data-testid="tab-branding">Branding</TabsTrigger>
          <TabsTrigger value="hours" data-testid="tab-hours">Hours</TabsTrigger>
          <TabsTrigger value="emergency" data-testid="tab-emergency">Emergency Rules</TabsTrigger>
          <TabsTrigger value="types" data-testid="tab-types">Appointment Types</TabsTrigger>
          {isSuperAdmin && <TabsTrigger value="retell" data-testid="tab-retell">Retell</TabsTrigger>}
        </TabsList>

        {/* Branding */}
        <TabsContent value="branding">
          <ErrorBoundary label="Branding" onReset={refreshPractice}>
          <Card><CardHeader><CardTitle>Branding</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div><Label>Agent name</Label><Input data-testid="settings-agent-name" value={branding.agent_name} onChange={e => setBranding({ ...branding, agent_name: e.target.value })} /></div>
              <div><Label>Voice tone</Label>
                <select className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={branding.voice_tone} onChange={e => setBranding({ ...branding, voice_tone: e.target.value })}>
                  <option value="warm_professional">Warm &amp; professional</option>
                  <option value="casual">Casual &amp; friendly</option>
                  <option value="formal">Polished &amp; formal</option>
                </select>
              </div>
              <div><Label>Greeting</Label><Textarea rows={2} value={branding.greeting} onChange={e => setBranding({ ...branding, greeting: e.target.value })} /></div>
              <div><Label>Closing</Label><Textarea rows={2} value={branding.closing} onChange={e => setBranding({ ...branding, closing: e.target.value })} /></div>
              <Button data-testid="save-branding-btn" disabled={saving} onClick={() => save(`/practice/${pid}/branding`, branding, 'Branding')}
                className="bg-teal-600 hover:bg-teal-700">
                {saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Save
              </Button>
            </CardContent>
          </Card>
          </ErrorBoundary>
        </TabsContent>

        {/* Hours */}
        <TabsContent value="hours">
          <ErrorBoundary label="Hours" onReset={refreshPractice}>
          <Card><CardHeader><CardTitle>Hours</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {DAY_KEYS.map(k => {
                const slot = hours.weekly[k];
                return (
                  <div key={k} className="flex items-center gap-3">
                    <div className="w-12 font-medium">{DAY_LABELS[k]}</div>
                    <input type="checkbox" checked={!!slot}
                      onChange={e => setHours(h => ({ ...h, weekly: { ...h.weekly, [k]: e.target.checked ? { open: '08:00', close: '17:00' } : null } }))} />
                    <Input type="time" value={slot?.open || ''} disabled={!slot}
                      onChange={e => setHours(h => ({ ...h, weekly: { ...h.weekly, [k]: { ...h.weekly[k], open: e.target.value } } }))} className="w-32" />
                    <span>–</span>
                    <Input type="time" value={slot?.close || ''} disabled={!slot}
                      onChange={e => setHours(h => ({ ...h, weekly: { ...h.weekly, [k]: { ...h.weekly[k], close: e.target.value } } }))} className="w-32" />
                  </div>
                );
              })}
              <Button data-testid="save-hours-btn" disabled={saving} onClick={() => save(`/practice/${pid}/hours`, hours, 'Hours')}
                className="bg-teal-600 hover:bg-teal-700">{saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Save</Button>
            </CardContent>
          </Card>
          </ErrorBoundary>
        </TabsContent>

        {/* Emergency */}
        <TabsContent value="emergency">
          <ErrorBoundary label="Emergency Rules" onReset={refreshPractice}>
          <Card><CardHeader><CardTitle>Emergency Rules</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div><Label>Trigger keywords (comma-separated)</Label>
                <Input value={emergency.triggers.join(', ')}
                  onChange={e => setEmergency({ ...emergency, triggers: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })} />
              </div>
              <div><Label>Response policy</Label>
                <select className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={emergency.response_policy} onChange={e => setEmergency({ ...emergency, response_policy: e.target.value })}>
                  <option value="earliest_available">Book earliest available</option>
                  <option value="transfer">Transfer to after-hours</option>
                  <option value="both">Book AND offer after-hours</option>
                </select>
              </div>
              <div><Label>After-hours handoff phone</Label>
                <Input value={emergency.after_hours_handoff_phone || ''} onChange={e => setEmergency({ ...emergency, after_hours_handoff_phone: e.target.value })} />
              </div>
              <Button data-testid="save-emergency-btn" disabled={saving} onClick={() => save(`/practice/${pid}/emergency-rules`, emergency, 'Emergency rules')}
                className="bg-teal-600 hover:bg-teal-700">{saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Save</Button>
            </CardContent>
          </Card>
          </ErrorBoundary>
        </TabsContent>

        {/* Appointment types */}
        <TabsContent value="types">
          <ErrorBoundary label="Appointment Types" onReset={refreshPractice}>
          <Card><CardHeader><CardTitle>Appointment Types</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {types.map(t => (
                <div key={t.id} className="flex items-center justify-between bg-slate-50 rounded px-3 py-2">
                  <span><strong>{t.name}</strong> <span className="text-slate-500 text-sm">· {t.duration_min} min · {t.id}</span></span>
                  <Button size="sm" variant="ghost"
                    onClick={async () => {
                      try { const r = await del(`/practice/${pid}/appointment-types/${t.id}`); setTypes(r.data); toast.success('Removed'); await refreshPractice(); }
                      catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
                    }}>Remove</Button>
                </div>
              ))}
              <div className="flex gap-2 items-end pt-2">
                <div className="flex-1"><Label>Name</Label><Input data-testid="new-type-name" value={newType.name} onChange={e => setNewType({ ...newType, name: e.target.value })} /></div>
                <div className="w-28"><Label>Duration</Label><Input type="number" value={newType.duration_min} onChange={e => setNewType({ ...newType, duration_min: parseInt(e.target.value || '30') })} /></div>
                <Button data-testid="add-type-btn" disabled={saving} onClick={async () => {
                  if (!newType.name.trim()) return toast.error('Enter a name');
                  const id = (newType.id || newType.name).toLowerCase().replace(/\s+/g, '-');
                  setSaving(true);
                  try { const r = await post(`/practice/${pid}/appointment-types`, { ...newType, id }); setTypes(r.data); setNewType({ id: '', name: '', duration_min: 30 }); toast.success('Added'); await refreshPractice(); }
                  catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
                  finally { setSaving(false); }
                }}>Add</Button>
              </div>
            </CardContent>
          </Card>
          </ErrorBoundary>
        </TabsContent>

        {/* Retell — super_admin only */}
        {isSuperAdmin && (
        <TabsContent value="retell">
          <ErrorBoundary label="Retell" onReset={refreshPractice}>
          <Card><CardHeader><CardTitle>Retell Configuration</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div><Label>Agent ID</Label><Input data-testid="retell-agent-id" value={retell.agent_id || ''} onChange={e => setRetell({ ...retell, agent_id: e.target.value })} /></div>
              <div><Label>Phone number</Label><Input data-testid="retell-phone" value={retell.phone_number || ''} onChange={e => setRetell({ ...retell, phone_number: e.target.value })} /></div>
              <Button data-testid="save-retell-btn" disabled={saving} onClick={() => save(`/practice/${pid}/config`, { retell }, 'Retell config')}
                className="bg-teal-600 hover:bg-teal-700">{saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Save</Button>

              <div className="pt-5 border-t mt-5">
                <div className="flex items-center justify-between mb-2">
                  <Label>Rendered system prompt</Label>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={regeneratePrompt}>Re-render</Button>
                    {prompt && <CopyInline text={prompt} />}
                  </div>
                </div>
                <Textarea rows={10} readOnly value={prompt || 'Click "Re-render" to load the current prompt with latest config.'}
                  data-testid="retell-prompt-preview" className="font-mono text-xs" />
                <p className="text-xs text-slate-500 mt-2">Paste this into your Retell agent's system prompt whenever you change hours, providers, branding, or rules.</p>
              </div>
            </CardContent>
          </Card>
          </ErrorBoundary>
        </TabsContent>
        )}

      </Tabs>
    </div>
  );
}
