import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Check,
  Copy,
  ChevronRight,
  ChevronLeft,
  Loader2,
  Phone,
  Clock,
  AlertTriangle,
  ClipboardList,
  Sparkles,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { toast } from 'sonner';

import { useAuth } from '@/hooks/useAuth';
import api from '@/lib/api';

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
const DAY_LABELS = {
  mon: 'Mon',
  tue: 'Tue',
  wed: 'Wed',
  thu: 'Thu',
  fri: 'Fri',
  sat: 'Sat',
  sun: 'Sun',
};

function CopyButton({ text, label = 'Copy' }) {
  const [copied, setCopied] = useState(false);

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          toast.error('Copy failed');
        }
      }}
    >
      {copied ? <Check className="w-4 h-4 mr-1" /> : <Copy className="w-4 h-4 mr-1" />}
      {copied ? 'Copied!' : label}
    </Button>
  );
}

export default function OnboardingWizard() {
  const navigate = useNavigate();
  const {
    user,
    practice,
    onboardPractice,
    completeOnboarding,
    refreshPractice,
    isSuperAdmin,
  } = useAuth();

  const [step, setStep] = useState(user && practice ? 2 : 0);
  const [saving, setSaving] = useState(false);

  const [signup, setSignup] = useState({
    practice_name: '',
    timezone: 'America/Toronto',
    admin_email: '',
    admin_password: '',
    admin_full_name: '',
    contact_phone: '',
  });

  const [hours, setHours] = useState({
    timezone: 'America/Toronto',
    weekly: {
      mon: { open: '08:00', close: '17:00' },
      tue: { open: '08:00', close: '17:00' },
      wed: { open: '08:00', close: '17:00' },
      thu: { open: '08:00', close: '17:00' },
      fri: { open: '08:00', close: '15:00' },
      sat: null,
      sun: null,
    },
    closed_dates: [],
  });

  const [providers, setProviders] = useState([]);
  const [newProvider, setNewProvider] = useState({ name: '', role: 'Dentist' });

  const [apptTypes, setApptTypes] = useState([]);
  const [newType, setNewType] = useState({ id: '', name: '', duration_min: 30 });

  const [branding, setBranding] = useState({
    agent_name: 'Amanda',
    greeting: '',
    closing: 'Thank you for calling. Have a great day!',
    voice_tone: 'warm_professional',
  });

  const [emergency, setEmergency] = useState({
    triggers: ['severe pain', 'swelling', 'bleeding', 'trauma'],
    response_policy: 'earliest_available',
    after_hours_handoff_phone: '',
  });

  const [retellPayload, setRetellPayload] = useState(null);
  const [retellAgentId, setRetellAgentId] = useState('');
  const [retellPhone, setRetellPhone] = useState('');

  useEffect(() => {
    if (practice?.settings) {
      setHours(practice.settings.hours || hours);
      setApptTypes(practice.settings.appointment_types || []);
      setBranding(practice.settings.branding || branding);
      setEmergency(practice.settings.emergency || emergency);
      setRetellAgentId(practice.settings.retell?.agent_id || '');
      setRetellPhone(practice.settings.retell?.phone_number || '');
    }
  }, [practice]);

  const next = () => setStep((s) => Math.min(s + 1, STEPS.length - 1));
  const back = () => setStep((s) => Math.max(s - 1, 0));

  const handleSignup = async () => {
    setSaving(true);
    try {
      await onboardPractice(signup);
      toast.success('Practice created!');
      next();
    } catch (err) {
      toast.error(err.message || 'Signup failed');
    } finally {
      setSaving(false);
    }
  };

  const saveHours = async () => {
    setSaving(true);
    try {
      await api.put('/practice/settings/hours', hours);
      toast.success('Hours saved');
      next();
    } catch (err) {
      toast.error('Failed to save hours');
    } finally {
      setSaving(false);
    }
  };

  const addProvider = async () => {
    if (!newProvider.name) return;
    setSaving(true);
    try {
      const res = await api.post('/practice/providers', newProvider);
      setProviders([...providers, res.data]);
      setNewProvider({ name: '', role: 'Dentist' });
      toast.success('Provider added');
    } catch {
      toast.error('Failed to add provider');
    } finally {
      setSaving(false);
    }
  };

  const removeProvider = async (id) => {
    setSaving(true);
    try {
      await api.delete(`/practice/providers/${id}`);
      setProviders(providers.filter((p) => p.id !== id));
      toast.success('Provider removed');
    } catch {
      toast.error('Failed to remove provider');
    } finally {
      setSaving(false);
    }
  };

  const addApptType = async () => {
    if (!newType.name) return;
    setSaving(true);
    try {
      const res = await api.post('/practice/appointment-types', newType);
      setApptTypes([...apptTypes, res.data]);
      setNewType({ id: '', name: '', duration_min: 30 });
      toast.success('Appointment type added');
    } catch {
      toast.error('Failed to add appointment type');
    } finally {
      setSaving(false);
    }
  };

  const removeApptType = async (id) => {
    setSaving(true);
    try {
      await api.delete(`/practice/appointment-types/${id}`);
      setApptTypes(apptTypes.filter((t) => t.id !== id));
      toast.success('Appointment type removed');
    } catch {
      toast.error('Failed to remove appointment type');
    } finally {
      setSaving(false);
    }
  };

  const saveBranding = async () => {
    setSaving(true);
    try {
      await api.put('/practice/settings/branding', branding);
      toast.success('Branding saved');
      next();
    } catch {
      toast.error('Failed to save branding');
    } finally {
      setSaving(false);
    }
  };

  const saveEmergency = async () => {
    setSaving(true);
    try {
      await api.put('/practice/settings/emergency', emergency);
      toast.success('Emergency rules saved');
      next();
    } catch {
      toast.error('Failed to save emergency rules');
    } finally {
      setSaving(false);
    }
  };

  const loadRetellPrompt = async () => {
    try {
      const res = await api.get('/practice/settings/retell/prompt');
      setRetellPayload(res.data);
    } catch {
      toast.error('Failed to load Retell prompt');
    }
  };

  const saveRetell = async () => {
    setSaving(true);
    try {
      await api.put('/practice/settings/retell', {
        agent_id: retellAgentId,
        phone_number: retellPhone,
      });
      toast.success('Retell settings saved');
      next();
    } catch {
      toast.error('Failed to save Retell settings');
    } finally {
      setSaving(false);
    }
  };

  const finish = async () => {
    setSaving(true);
    try {
      await completeOnboarding();
      toast.success('Onboarding complete!');
      navigate('/dashboard');
    } catch {
      toast.error('Failed to finish onboarding');
    } finally {
      setSaving(false);
    }
  };

  const StepWrapper = ({ children }) => (
    <Card className="max-w-3xl mx-auto mt-10 shadow-lg">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {React.createElement(STEPS[step].icon, { className: 'w-5 h-5 text-blue-600' })}
          {STEPS[step].name}
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );

  return (
    <div className="p-6">
      {/* Step Navigation */}
      <div className="flex justify-center gap-2 mb-6">
        {STEPS.map((s) => (
          <div
            key={s.id}
            className={`px-3 py-1 rounded-full text-sm ${
              step === s.id ? 'bg-blue-600 text-white' : 'bg-gray-200'
            }`}
          >
            {s.name}
          </div>
        ))}
      </div>

      {/* Step 0 — Welcome */}
      {step === 0 && (
        <StepWrapper>
          <p className="text-gray-700 mb-4">
            Welcome to Dental AI! Let's get your practice set up.
          </p>
          <Button onClick={next}>Get Started</Button>
        </StepWrapper>
      )}

      {/* Step 1 — Practice Basics */}
      {step === 1 && (
        <StepWrapper>
          <div className="space-y-4">
            <div>
              <Label>Practice Name</Label>
              <Input
                value={signup.practice_name}
                onChange={(e) =>
                  setSignup({ ...signup, practice_name: e.target.value })
                }
              />
            </div>

            <div>
              <Label>Admin Full Name</Label>
              <Input
                value={signup.admin_full_name}
                onChange={(e) =>
                  setSignup({ ...signup, admin_full_name: e.target.value })
                }
              />
            </div>

            <div>
              <Label>Admin Email</Label>
              <Input
                type="email"
                value={signup.admin_email}
                onChange={(e) =>
                  setSignup({ ...signup, admin_email: e.target.value })
                }
              />
            </div>

            <div>
              <Label>Password</Label>
              <Input
                type="password"
                value={signup.admin_password}
                onChange={(e) =>
                  setSignup({ ...signup, admin_password: e.target.value })
                }
              />
            </div>

            <div>
              <Label>Contact Phone</Label>
              <Input
                value={signup.contact_phone}
                onChange={(e) =>
                  setSignup({ ...signup, contact_phone: e.target.value })
                }
              />
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={back}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
              <Button onClick={handleSignup} disabled={saving}>
                {saving ? <Loader2 className="animate-spin" /> : 'Save & Continue'}
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Step 2 — Hours */}
      {step === 2 && (
        <StepWrapper>
          <div className="space-y-4">
            {DAY_KEYS.map((day) => (
              <div key={day} className="flex items-center gap-4">
                <Label className="w-16">{DAY_LABELS[day]}</Label>

                {hours.weekly[day] ? (
                  <>
                    <Input
                      type="time"
                      value={hours.weekly[day].open}
                      onChange={(e) =>
                        setHours({
                          ...hours,
                          weekly: {
                            ...hours.weekly,
                            [day]: {
                              ...hours.weekly[day],
                              open: e.target.value,
                            },
                          },
                        })
                      }
                    />
                    <Input
                      type="time"
                      value={hours.weekly[day].close}
                      onChange={(e) =>
                        setHours({
                          ...hours,
                          weekly: {
                            ...hours.weekly,
                            [day]: {
                              ...hours.weekly[day],
                              close: e.target.value,
                            },
                          },
                        })
                      }
                    />
                    <Button
                      variant="outline"
                      onClick={() =>
                        setHours({
                          ...hours,
                          weekly: { ...hours.weekly, [day]: null },
                        })
                      }
                    >
                      Closed
                    </Button>
                  </>
                ) : (
                  <Button
                    onClick={() =>
                      setHours({
                        ...hours,
                        weekly: {
                          ...hours.weekly,
                          [day]: { open: '09:00', close: '17:00' },
                        },
                      })
                    }
                  >
                    Set Hours
                  </Button>
                )}
              </div>
            ))}

            <div className="flex justify-between">
              <Button variant="outline" onClick={back}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
              <Button onClick={saveHours} disabled={saving}>
                {saving ? <Loader2 className="animate-spin" /> : 'Save & Continue'}
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Step 3 — Providers */}
      {step === 3 && (
        <StepWrapper>
          <div className="space-y-4">
            <div className="flex gap-4">
              <Input
                placeholder="Provider Name"
                value={newProvider.name}
                onChange={(e) =>
                  setNewProvider({ ...newProvider, name: e.target.value })
                }
              />
              <Input
                placeholder="Role"
                value={newProvider.role}
                onChange={(e) =>
                  setNewProvider({ ...newProvider, role: e.target.value })
                }
              />
              <Button onClick={addProvider} disabled={saving}>
                Add
              </Button>
            </div>

            <div className="space-y-2">
              {providers.map((p) => (
                <div
                  key={p.id}
                  className="flex justify-between items-center p-2 border rounded"
                >
                  <span>
                    {p.name} — {p.role}
                  </span>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => removeProvider(p.id)}
                  >
                    Remove
                  </Button>
                </div>
              ))}
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={back}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
              <Button onClick={next}>
                Continue
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Step 4 — Appointment Types */}
      {step === 4 && (
        <StepWrapper>
          <div className="space-y-4">
            <div className="flex gap-4">
              <Input
                placeholder="Type Name"
                value={newType.name}
                onChange={(e) =>
                  setNewType({ ...newType, name: e.target.value })
                }
              />
              <Input
                type="number"
                placeholder="Duration (min)"
                value={newType.duration_min}
                onChange={(e) =>
                  setNewType({
                    ...newType,
                    duration_min: Number(e.target.value),
                  })
                }
              />
              <Button onClick={addApptType} disabled={saving}>
                Add
              </Button>
            </div>

            <div className="space-y-2">
              {apptTypes.map((t) => (
                <div
                  key={t.id}
                  className="flex justify-between items-center p-2 border rounded"
                >
                  <span>
                    {t.name} — {t.duration_min} min
                  </span>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => removeApptType(t.id)}
                  >
                    Remove
                  </Button>
                </div>
              ))}
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={back}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
              <Button onClick={next}>
                Continue
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </StepWrapper>
      )}
{/* Step 5 — Branding */}
{step === 5 && (
  <StepWrapper>
    <div className="space-y-4">
      <div>
        <Label>AI Receptionist Name</Label>
        <Input
          value={branding.agent_name}
          onChange={(e) =>
            setBranding({ ...branding, agent_name: e.target.value })
          }
        />
      </div>

      <div>
        <Label>Greeting</Label>
        <Input
          placeholder="Hi, thank you for calling..."
          value={branding.greeting}
          onChange={(e) =>
            setBranding({ ...branding, greeting: e.target.value })
          }
        />
      </div>

      <div>
        <Label>Closing Line</Label>
        <Input
          value={branding.closing}
          onChange={(e) =>
            setBranding({ ...branding, closing: e.target.value })
          }
        />
      </div>

      <div>
        <Label>Voice Tone</Label>
        <select
          className="border rounded p-2 w-full"
          value={branding.voice_tone}
          onChange={(e) =>
            setBranding({ ...branding, voice_tone: e.target.value })
          }
        >
          <option value="warm_professional">Warm & Professional</option>
          <option value="friendly">Friendly</option>
          <option value="formal">Formal</option>
          <option value="energetic">Energetic</option>
        </select>
      </div>

      <div className="flex justify-between">
        <Button variant="outline" onClick={back}>
          <ChevronLeft className="w-4 h-4 mr-1" />
          Back
        </Button>
        <Button onClick={saveBranding} disabled={saving}>
          {saving ? <Loader2 className="animate-spin" /> : 'Save & Continue'}
          <ChevronRight className="w-4 h-4 ml-1" />
        </Button>
      </div>
    </div>
  </StepWrapper>
)}

      {/* Step 6 — Emergency Rules */}
      {step === 6 && (
        <StepWrapper>
          <div className="space-y-4">
            <div>
              <Label>Emergency Trigger Keywords</Label>
              <Input
                value={emergency.triggers.join(', ')}
                onChange={(e) =>
                  setEmergency({
                    ...emergency,
                    triggers: e.target.value.split(',').map((t) => t.trim()),
                  })
                }
              />
            </div>

            <div>
              <Label>Response Policy</Label>
              <select
                className="border rounded p-2 w-full"
                value={emergency.response_policy}
                onChange={(e) =>
                  setEmergency({
                    ...emergency,
                    response_policy: e.target.value,
                  })
                }
              >
                <option value="earliest_available">Earliest Available</option>
                <option value="same_day_if_possible">Same Day If Possible</option>
                <option value="redirect_to_emergency_line">
                  Redirect to Emergency Line
                </option>
              </select>
            </div>

            <div>
              <Label>After-Hours Emergency Phone</Label>
              <Input
                value={emergency.after_hours_handoff_phone}
                onChange={(e) =>
                  setEmergency({
                    ...emergency,
                    after_hours_handoff_phone: e.target.value,
                  })
                }
              />
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={back}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
              <Button onClick={saveEmergency} disabled={saving}>
                {saving ? <Loader2 className="animate-spin" /> : 'Save & Continue'}
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Step 7 — Retell Setup */}
      {step === 7 && (
        <StepWrapper>
          <div className="space-y-4">
            <p className="text-gray-700">
              Connect your Retell voice agent. This enables phone call automation.
            </p>

            <div>
              <Label>Retell Agent ID</Label>
              <Input
                value={retellAgentId}
                onChange={(e) => setRetellAgentId(e.target.value)}
              />
            </div>

            <div>
              <Label>Retell Phone Number</Label>
              <Input
                value={retellPhone}
                onChange={(e) => setRetellPhone(e.target.value)}
              />
            </div>

            <div>
              <Button variant="outline" onClick={loadRetellPrompt}>
                Load Retell Prompt
              </Button>
            </div>

            {retellPayload && (
              <div className="p-3 border rounded bg-gray-50">
                <pre className="text-xs whitespace-pre-wrap">
                  {JSON.stringify(retellPayload, null, 2)}
                </pre>
                <CopyButton text={JSON.stringify(retellPayload, null, 2)} />
              </div>
            )}

            <div className="flex justify-between">
              <Button variant="outline" onClick={back}>
                <ChevronLeft className="w-4 h-4 mr-1" />
                Back
              </Button>
              <Button onClick={saveRetell} disabled={saving}>
                {saving ? <Loader2 className="animate-spin" /> : 'Save & Continue'}
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </StepWrapper>
      )}

      {/* Step 8 — Test & Finish */}
      {step === 8 && (
        <StepWrapper>
          <div className="space-y-4">
            <p className="text-gray-700">
              Your practice setup is complete! You can now test your AI receptionist
              and begin using Dental AI.
            </p>

            <Button
              className="w-full"
              onClick={finish}
              disabled={saving}
            >
              {saving ? <Loader2 className="animate-spin" /> : 'Finish & Go to Dashboard'}
            </Button>

            <Button
              variant="outline"
              className="w-full"
              onClick={() => navigate('/dashboard')}
            >
              Skip for now
            </Button>
          </div>
        </StepWrapper>
      )}
    </div>
  );
}
