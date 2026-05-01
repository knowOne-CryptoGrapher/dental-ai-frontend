import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import { Check, Copy, ChevronRight, ChevronLeft, Loader2, Phone, Clock, AlertTriangle, ClipboardList, Sparkles } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const STEPS = [
  { id: 0, name: 'Welcome', icon: Sparkles },
  { id: 1, name: 'Practice Basics', icon: ClipboardList },
  { id: 2, name: 'Hours', icon: Clock },
  { id: 3, name: 'Providers', icon: ClipboardList },
  { id: 4, name: 'Appointment Types', icon: ClipboardList },
  { id: 5, name: 'Branding', icon: Sparkles },
  { id: 6, name: 'Emergency Rules', icon: AlertTriangle },
  { id: 7, name: 'Retell Setup', icon: Phone },
  { id: 8, name: 'Test & Finish', icon: Check },
];

const DAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'];
const DAY_LABELS = { mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri', sat: 'Sat', sun: 'Sun' };

function CopyButton({ text, label = 'Copy' }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="outline" size="sm"
      data-testid="copy-btn"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true); setTimeout(() => setCopied(false), 1500);
        } catch { toast.error('Copy failed'); }
      }}>
      {copied ? <Check className="w-4 h-4 mr-1" /> : <Copy className="w-4 h-4 mr-1" />}
      {copied ? 'Copied!' : label}
    </Button>
  );
}

export default function OnboardingWizard() {
  const navigate = useNavigate();
  const { user, practice, token, onboardPractice, completeOnboarding, refreshPractice, axiosAuth, isSuperAdmin } = useAuth();

  const [step, setStep] = useState(user && practice ? 2 : 0);  // skip signup if already in
  const [saving, setSaving] = useState(false);

  // Signup form
  const [signup, setSignup] = useState({
    practice_name: '', timezone: 'America/Toronto',
    admin_email: '', admin_password: '', admin_full_name: '',
    contact_phone: '',
  });

  // Hours form (Mon–Fri 8-5 default)
  const [hours, setHours] = useState({
    timezone: 'America/Toronto',
    weekly: {
      mon: { open: '08:00', close: '17:00' },
      tue: { open: '08:00', close: '17:00' },
      wed: { open: '08:00', close: '17:00' },
      thu: { open: '08:00', close: '17:00' },
      fri: { open: '08:00', close: '15:00' },
      sat: null, sun: null,
    },
    closed_dates: [],
  });

  // Providers list (local until saved)
  const [providers, setProviders] = useState([]);
  const [newProvider, setNewProvider] = useState({ name: '', role: 'Dentist' });

  // Appointment types
  const [apptTypes, setApptTypes] = useState([]);
  const [newType, setNewType] = useState({ id: '', name: '', duration_min: 30 });

  // Branding
  const [branding, setBranding] = useState({
    agent_name: 'Amanda', greeting: '', closing: 'Thank you for calling. Have a great day!', voice_tone: 'warm_professional',
  });

  // Emergency
  const [emergency, setEmergency] = useState({
    triggers: ['severe pain', 'swelling', 'bleeding', 'trauma'],
    response_policy: 'earliest_available',
    after_hours_handoff_phone: '',
  });

  // Retell step state
  const [retellPayload, setRetellPayload] = useState(null);
  const [retellAgentId, setRetellAgentId] = useState('');
  const [retellPhone, setRetellPhone] = useState('');

  // Hydrate from backend when practice changes
  useEffect(() => {
    if (practice?.settings) {
      setHours(practice.settings.hours || hours);
      setApptTypes(practice.settings.appointment_types || []);
      setBranding(practice.settings.branding || branding);
      setEmergency(practice.settings.emergency || emergency);
      setRetellAgentId(practice.settings.retell?.agent_id || '');
      setRetellPhone(practice.settings.retell?.phone_number || '');
    }
  }, [practice]); // eslint-disable-line

  // Fetch providers when we reach step 3
  useEffect(() => {
    if (step === 3 && user?.practice_id) {
      axiosAuth().get('/providers').then(r => setProviders(r.data || [])).catch(() => {});
    }
  }, [step, user]); // eslint-disable-line

  // Persist API helpers
  const put = async (path, body) => axiosAuth().put(path, body);
  const post = async (path, body) => axiosAuth().post(path, body);
  const del = async (path) => axiosAuth().delete(path);

  // ── Step handlers ─────────────────────────────────────────────

  const handleSignup = async () => {
    setSaving(true);
    try {
      const data = await onboardPractice(signup);
      setRetellPayload(data.next_steps);
      // Seed branding greeting with practice name
      setBranding(b => ({ ...b, greeting: `Thank you for calling ${signup.practice_name}! This is ${b.agent_name}. How can I help today?` }));
      toast.success('Practice created!');
      setStep(2);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Signup failed');
    } finally { setSaving(false); }
  };

  const handleSaveHours = async () => {
    setSaving(true);
    try {
      await put(`/practice/${user.practice_id}/hours`, hours);
      toast.success('Hours saved');
      setStep(3);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setSaving(false); }
  };

  const addProvider = async () => {
    if (!newProvider.name.trim()) return toast.error('Enter a name');
    setSaving(true);
    try {
      await post('/providers', {
        name: newProvider.name.trim(),
        role: newProvider.role,
        appointment_types: [], working_hours: {}, on_call: false,
        specialties: [], license_number: '',
      });
      // Refetch
      const r = await axiosAuth().get('/providers');
      setProviders(r.data || []);
      setNewProvider({ name: '', role: 'Dentist' });
      toast.success('Provider added');
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setSaving(false); }
  };

  const removeProvider = async (id) => {
    try { await del(`/providers/${id}`); const r = await axiosAuth().get('/providers'); setProviders(r.data || []); }
    catch { toast.error('Failed'); }
  };

  const addType = async () => {
    if (!newType.name.trim()) return toast.error('Enter a name');
    const id = (newType.id || newType.name).toLowerCase().replace(/\s+/g, '-');
    setSaving(true);
    try {
      const r = await post(`/practice/${user.practice_id}/appointment-types`, { ...newType, id });
      setApptTypes(r.data);
      setNewType({ id: '', name: '', duration_min: 30 });
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setSaving(false); }
  };

  const removeType = async (id) => {
    try { const r = await del(`/practice/${user.practice_id}/appointment-types/${id}`); setApptTypes(r.data); }
    catch { toast.error('Failed'); }
  };

  const saveBranding = async () => {
    setSaving(true);
    try { await put(`/practice/${user.practice_id}/branding`, branding); toast.success('Branding saved'); setStep(6); }
    catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setSaving(false); }
  };

  const saveEmergency = async () => {
    setSaving(true);
    try {
      await put(`/practice/${user.practice_id}/emergency-rules`, emergency);
      toast.success('Emergency rules saved');
      // Practice admins skip Step 7 (Retell setup is super_admin-only).
      // The platform owner provisions Retell for them out of band.
      setStep(isSuperAdmin ? 7 : 8);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setSaving(false); }
  };

  const loadRetellPrompt = async () => {
    try {
      const r = await axiosAuth().get(`/agent/${user.practice_id}/prompt`);
      setRetellPayload(prev => ({ ...(prev || {}), rendered_prompt: r.data.prompt }));
    } catch { toast.error('Failed to load prompt'); }
  };

  const saveRetellConfig = async () => {
    setSaving(true);
    try {
      await put(`/practice/${user.practice_id}/config`, {
        retell: { agent_id: retellAgentId || null, phone_number: retellPhone || null, provisioned_at: new Date().toISOString() }
      });
      toast.success('Retell config saved');
      setStep(8);
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    finally { setSaving(false); }
  };

  const finishOnboarding = async () => {
    setSaving(true);
    try {
      await completeOnboarding(user.practice_id);
      await refreshPractice();
      toast.success('Welcome aboard — your clinic is live!');
      navigate('/dashboard');
    } catch { toast.error('Could not finalize onboarding'); }
    finally { setSaving(false); }
  };

  // Build Retell payload URLs once we're in-session (fallback when payload missing)
  const urls = retellPayload?.function_urls || {
    lookup_patient:              `${BACKEND_URL}/api/retell/lookup-patient`,
    list_providers:              `${BACKEND_URL}/api/retell/list-providers`,
    check_provider_availability: `${BACKEND_URL}/api/retell/check-provider-availability`,
    book_appointments:           `${BACKEND_URL}/api/retell/book-appointment`,
    get_patient_appointments:    `${BACKEND_URL}/api/retell/get-patient-appointments`,
    cancel_appointment:          `${BACKEND_URL}/api/retell/cancel-appointment`,
    register_patient:            `${BACKEND_URL}/api/retell/register-patient`,
  };
  const webhookUrl = retellPayload?.webhook_url || `${BACKEND_URL}/api/webhooks/retell/${user?.practice_id}`;

  // ── Render ─────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-teal-50/30 py-8" data-testid="onboarding-wizard">
      <div className="max-w-4xl mx-auto px-4">

        {/* Progress bar */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-2">
            <h1 className="text-2xl font-bold text-slate-900">Welcome to DentalAI</h1>
            <span className="text-sm text-slate-500">Step {step + 1} of {STEPS.length}</span>
          </div>
          <div className="w-full bg-slate-200 rounded-full h-1.5">
            <div className="bg-teal-600 h-1.5 rounded-full transition-all" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            {STEPS.map((s, i) => (
              <span key={s.id}
                className={`px-2 py-1 rounded-full ${i === step ? 'bg-teal-600 text-white' : i < step ? 'bg-teal-100 text-teal-700' : 'bg-slate-100 text-slate-500'}`}>
                {s.name}
              </span>
            ))}
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{STEPS[step].name}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">

            {/* Step 0: Welcome */}
            {step === 0 && (
              <div className="space-y-4" data-testid="step-welcome">
                <p className="text-slate-700">Let's get your clinic set up with an AI receptionist. It takes about 20 minutes and includes:</p>
                <ul className="space-y-1.5 text-sm text-slate-600 list-disc pl-5">
                  <li>Creating your account & practice</li>
                  <li>Setting hours, providers, appointment types</li>
                  <li>Customizing your AI's greeting and emergency rules</li>
                  <li>Connecting your Retell phone number</li>
                </ul>
                <Button data-testid="wizard-start-btn" onClick={() => setStep(1)} className="bg-teal-600 hover:bg-teal-700">
                  Let's go <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            )}

            {/* Step 1: Signup */}
            {step === 1 && (
              <div className="space-y-4" data-testid="step-signup">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div><Label>Practice name *</Label><Input data-testid="signup-practice-name" value={signup.practice_name} onChange={e => setSignup({ ...signup, practice_name: e.target.value })} /></div>
                  <div><Label>Timezone</Label>
                    <select className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                      value={signup.timezone} onChange={e => setSignup({ ...signup, timezone: e.target.value })}>
                      <option value="America/Toronto">Eastern (Toronto)</option>
                      <option value="America/Halifax">Atlantic (Halifax)</option>
                      <option value="America/Winnipeg">Central (Winnipeg)</option>
                      <option value="America/Edmonton">Mountain (Edmonton)</option>
                      <option value="America/Vancouver">Pacific (Vancouver)</option>
                      <option value="America/New_York">US Eastern</option>
                      <option value="America/Chicago">US Central</option>
                      <option value="America/Denver">US Mountain</option>
                      <option value="America/Los_Angeles">US Pacific</option>
                    </select>
                  </div>
                  <div><Label>Contact phone</Label><Input data-testid="signup-contact-phone" value={signup.contact_phone} onChange={e => setSignup({ ...signup, contact_phone: e.target.value })} /></div>
                  <div><Label>Your full name *</Label><Input data-testid="signup-admin-name" value={signup.admin_full_name} onChange={e => setSignup({ ...signup, admin_full_name: e.target.value })} /></div>
                  <div><Label>Admin email *</Label><Input data-testid="signup-admin-email" type="email" value={signup.admin_email} onChange={e => setSignup({ ...signup, admin_email: e.target.value })} /></div>
                  <div><Label>Password *</Label><Input data-testid="signup-admin-password" type="password" value={signup.admin_password} onChange={e => setSignup({ ...signup, admin_password: e.target.value })} /></div>
                </div>
                <div className="flex justify-between">
                  <Button variant="outline" onClick={() => setStep(0)}><ChevronLeft className="w-4 h-4 mr-1" /> Back</Button>
                  <Button data-testid="wizard-signup-btn" onClick={handleSignup}
                    disabled={saving || !signup.practice_name || !signup.admin_email || !signup.admin_password || !signup.admin_full_name}
                    className="bg-teal-600 hover:bg-teal-700">
                    {saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Create practice <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              </div>
            )}

            {/* Step 2: Hours */}
            {step === 2 && (
              <div className="space-y-3" data-testid="step-hours">
                <p className="text-sm text-slate-600">Set weekly opening hours. Leave a day blank to mark it closed.</p>
                {DAY_KEYS.map(k => {
                  const slot = hours.weekly[k];
                  return (
                    <div key={k} className="flex items-center gap-3">
                      <div className="w-12 font-medium text-slate-700">{DAY_LABELS[k]}</div>
                      <input type="checkbox" checked={!!slot}
                        data-testid={`hours-${k}-open-toggle`}
                        onChange={e => setHours(h => ({ ...h, weekly: { ...h.weekly, [k]: e.target.checked ? { open: '08:00', close: '17:00' } : null } }))} />
                      <Input type="time" value={slot?.open || ''} disabled={!slot}
                        data-testid={`hours-${k}-open`}
                        onChange={e => setHours(h => ({ ...h, weekly: { ...h.weekly, [k]: { ...h.weekly[k], open: e.target.value } } }))}
                        className="w-32" />
                      <span>–</span>
                      <Input type="time" value={slot?.close || ''} disabled={!slot}
                        data-testid={`hours-${k}-close`}
                        onChange={e => setHours(h => ({ ...h, weekly: { ...h.weekly, [k]: { ...h.weekly[k], close: e.target.value } } }))}
                        className="w-32" />
                    </div>
                  );
                })}
                <div className="flex justify-between pt-3">
                  <Button variant="outline" onClick={() => setStep(1)}><ChevronLeft className="w-4 h-4 mr-1" /> Back</Button>
                  <Button data-testid="hours-save-btn" onClick={handleSaveHours} disabled={saving} className="bg-teal-600 hover:bg-teal-700">
                    {saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Save & continue <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              </div>
            )}

            {/* Step 3: Providers */}
            {step === 3 && (
              <div className="space-y-3" data-testid="step-providers">
                <p className="text-sm text-slate-600">Add at least one provider. Names are auto-titled ("Dr." prefix for doctor roles).</p>
                <div className="space-y-2">
                  {providers.map(p => (
                    <div key={p.id} className="flex items-center justify-between bg-slate-50 rounded px-3 py-2" data-testid={`provider-${p.id}`}>
                      <span><strong>{p.name}</strong> <span className="text-slate-500 text-sm">· {p.role}</span></span>
                      <Button size="sm" variant="ghost" onClick={() => removeProvider(p.id)}>Remove</Button>
                    </div>
                  ))}
                  {providers.length === 0 && <p className="text-sm text-slate-400 italic">No providers added yet.</p>}
                </div>
                <div className="flex gap-2 items-end pt-2">
                  <div className="flex-1"><Label>Name</Label><Input data-testid="new-provider-name" placeholder="john smith" value={newProvider.name} onChange={e => setNewProvider({ ...newProvider, name: e.target.value })} /></div>
                  <div className="w-40"><Label>Role</Label>
                    <select className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                      data-testid="new-provider-role"
                      value={newProvider.role} onChange={e => setNewProvider({ ...newProvider, role: e.target.value })}>
                      <option>Dentist</option>
                      <option>Hygienist</option>
                      <option>Orthodontist</option>
                      <option>Oral Surgeon</option>
                    </select>
                  </div>
                  <Button data-testid="add-provider-btn" onClick={addProvider} disabled={saving}>Add</Button>
                </div>
                <div className="flex justify-between pt-3">
                  <Button variant="outline" onClick={() => setStep(2)}><ChevronLeft className="w-4 h-4 mr-1" /> Back</Button>
                  <Button data-testid="providers-next-btn" onClick={() => setStep(4)} disabled={providers.length === 0} className="bg-teal-600 hover:bg-teal-700">
                    Continue <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              </div>
            )}

            {/* Step 4: Appointment types */}
            {step === 4 && (
              <div className="space-y-3" data-testid="step-types">
                <p className="text-sm text-slate-600">Default types ship pre-loaded. Add custom ones if you offer specialty services.</p>
                <div className="space-y-2">
                  {apptTypes.map(t => (
                    <div key={t.id} className="flex items-center justify-between bg-slate-50 rounded px-3 py-2">
                      <span><strong>{t.name}</strong> <span className="text-slate-500 text-sm">· {t.duration_min} min</span></span>
                      <Button size="sm" variant="ghost" onClick={() => removeType(t.id)}>Remove</Button>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2 items-end pt-2">
                  <div className="flex-1"><Label>Name</Label><Input data-testid="new-type-name" placeholder="Whitening" value={newType.name} onChange={e => setNewType({ ...newType, name: e.target.value })} /></div>
                  <div className="w-28"><Label>Duration (min)</Label><Input data-testid="new-type-duration" type="number" value={newType.duration_min} onChange={e => setNewType({ ...newType, duration_min: parseInt(e.target.value || '30') })} /></div>
                  <Button data-testid="add-type-btn" onClick={addType} disabled={saving}>Add</Button>
                </div>
                <div className="flex justify-between pt-3">
                  <Button variant="outline" onClick={() => setStep(3)}><ChevronLeft className="w-4 h-4 mr-1" /> Back</Button>
                  <Button data-testid="types-next-btn" onClick={() => setStep(5)} className="bg-teal-600 hover:bg-teal-700">Continue <ChevronRight className="w-4 h-4 ml-1" /></Button>
                </div>
              </div>
            )}

            {/* Step 5: Branding */}
            {step === 5 && (
              <div className="space-y-3" data-testid="step-branding">
                <div><Label>AI receptionist's name</Label><Input data-testid="branding-agent-name" value={branding.agent_name} onChange={e => setBranding({ ...branding, agent_name: e.target.value })} /></div>
                <div><Label>Voice tone</Label>
                  <select className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                    data-testid="branding-tone"
                    value={branding.voice_tone} onChange={e => setBranding({ ...branding, voice_tone: e.target.value })}>
                    <option value="warm_professional">Warm &amp; professional</option>
                    <option value="casual">Casual &amp; friendly</option>
                    <option value="formal">Polished &amp; formal</option>
                  </select>
                </div>
                <div><Label>Greeting</Label><Textarea data-testid="branding-greeting" rows={2} value={branding.greeting} onChange={e => setBranding({ ...branding, greeting: e.target.value })} /></div>
                <div><Label>Closing line</Label><Textarea data-testid="branding-closing" rows={2} value={branding.closing} onChange={e => setBranding({ ...branding, closing: e.target.value })} /></div>
                <div className="flex justify-between pt-3">
                  <Button variant="outline" onClick={() => setStep(4)}><ChevronLeft className="w-4 h-4 mr-1" /> Back</Button>
                  <Button data-testid="branding-save-btn" onClick={saveBranding} disabled={saving} className="bg-teal-600 hover:bg-teal-700">
                    {saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Save & continue
                  </Button>
                </div>
              </div>
            )}

            {/* Step 6: Emergency */}
            {step === 6 && (
              <div className="space-y-3" data-testid="step-emergency">
                <div>
                  <Label>Emergency trigger keywords</Label>
                  <Input data-testid="emergency-triggers"
                    value={emergency.triggers.join(', ')}
                    onChange={e => setEmergency({ ...emergency, triggers: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })} />
                  <p className="text-xs text-slate-500 mt-1">Comma-separated. Amanda will flag any caller using these words as an emergency.</p>
                </div>
                <div><Label>Response policy</Label>
                  <select className="flex h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                    data-testid="emergency-policy"
                    value={emergency.response_policy} onChange={e => setEmergency({ ...emergency, response_policy: e.target.value })}>
                    <option value="earliest_available">Book earliest available slot</option>
                    <option value="transfer">Transfer to after-hours line</option>
                    <option value="both">Book slot AND offer after-hours line</option>
                  </select>
                </div>
                <div>
                  <Label>After-hours handoff phone (optional)</Label>
                  <Input data-testid="emergency-handoff-phone"
                    placeholder="+15551112222"
                    value={emergency.after_hours_handoff_phone || ''}
                    onChange={e => setEmergency({ ...emergency, after_hours_handoff_phone: e.target.value })} />
                </div>
                <div className="flex justify-between pt-3">
                  <Button variant="outline" onClick={() => setStep(5)}><ChevronLeft className="w-4 h-4 mr-1" /> Back</Button>
                  <Button data-testid="emergency-save-btn" onClick={saveEmergency} disabled={saving} className="bg-teal-600 hover:bg-teal-700">
                    {saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Save & continue
                  </Button>
                </div>
              </div>
            )}

            {/* Step 7: Retell setup (SUPER_ADMIN ONLY) */}
            {step === 7 && isSuperAdmin && (
              <div className="space-y-4" data-testid="step-retell">
                <div className="bg-amber-50 border border-amber-200 rounded p-3 text-sm text-amber-800">
                  <strong>Follow these steps in a new tab:</strong> Retell dashboard → create agent → paste prompt → add 7 custom functions with the URLs below → save the webhook URL → buy a phone number → paste the agent ID and phone back here.
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <Label>System prompt</Label>
                    {!retellPayload?.rendered_prompt && <Button size="sm" variant="ghost" onClick={loadRetellPrompt}>Load latest</Button>}
                    {retellPayload?.rendered_prompt && <CopyButton text={retellPayload.rendered_prompt} label="Copy prompt" />}
                  </div>
                  <Textarea rows={10} readOnly value={retellPayload?.rendered_prompt || 'Click "Load latest" to render your prompt.'}
                    data-testid="retell-prompt" className="font-mono text-xs" />
                </div>

                <div>
                  <Label>Function URLs (paste each into its matching Retell custom function)</Label>
                  <div className="space-y-1.5 mt-1">
                    {Object.entries(urls).map(([name, url]) => (
                      <div key={name} className="flex items-center gap-2 bg-slate-50 rounded px-3 py-2 text-sm">
                        <code className="flex-1 truncate"><strong>{name}</strong> → {url}</code>
                        <CopyButton text={url} label="Copy URL" />
                      </div>
                    ))}
                  </div>
                </div>

                <div>
                  <Label>Webhook URL (paste into Retell → Agent → Webhook)</Label>
                  <div className="flex items-center gap-2 bg-slate-50 rounded px-3 py-2 text-sm">
                    <code className="flex-1 truncate">{webhookUrl}</code>
                    <CopyButton text={webhookUrl} />
                  </div>
                </div>

                <div className="pt-3 border-t grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <Label>Retell agent ID</Label>
                    <Input data-testid="retell-agent-id" placeholder="agent_xxxx" value={retellAgentId} onChange={e => setRetellAgentId(e.target.value)} />
                  </div>
                  <div>
                    <Label>Retell phone number</Label>
                    <Input data-testid="retell-phone" placeholder="+15551112222" value={retellPhone} onChange={e => setRetellPhone(e.target.value)} />
                  </div>
                </div>

                <div className="flex justify-between pt-3">
                  <Button variant="outline" onClick={() => setStep(6)}><ChevronLeft className="w-4 h-4 mr-1" /> Back</Button>
                  <Button data-testid="retell-save-btn" onClick={saveRetellConfig} disabled={saving} className="bg-teal-600 hover:bg-teal-700">
                    {saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Save & continue
                  </Button>
                </div>
              </div>
            )}

            {/* Step 8: Finish */}
            {step === 8 && (
              <div className="space-y-4 text-center py-6" data-testid="step-finish">
                <div className="mx-auto w-16 h-16 rounded-full bg-teal-100 flex items-center justify-center">
                  <Check className="w-8 h-8 text-teal-600" />
                </div>
                <h3 className="text-xl font-semibold">You're all set!</h3>
                <p className="text-slate-600">{isSuperAdmin
                  ? `Your AI receptionist is ready. Place a test call to ${retellPhone || 'your Retell number'} to verify the setup.`
                  : `Your account is ready. Our team will provision your AI receptionist phone number and you'll receive an email once it's live — usually within one business day.`}</p>
                <Button data-testid="finish-btn" onClick={finishOnboarding} disabled={saving} className="bg-teal-600 hover:bg-teal-700">
                  {saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Enter dashboard
                </Button>
              </div>
            )}

          </CardContent>
        </Card>
      </div>
    </div>
  );
}
