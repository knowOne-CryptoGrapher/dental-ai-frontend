import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Switch } from '../components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Mic, Phone, Shield, Database, Clock, Save, Loader2,
  RefreshCw, FileText, CheckCircle2
} from 'lucide-react';

const voiceModels = [
  { id: 'Polly.Joanna', name: 'Joanna', desc: 'Female, warm & professional', lang: 'en-US' },
  { id: 'Polly.Matthew', name: 'Matthew', desc: 'Male, clear & friendly', lang: 'en-US' },
  { id: 'Polly.Salli', name: 'Salli', desc: 'Female, natural tone', lang: 'en-US' },
  { id: 'Polly.Kimberly', name: 'Kimberly', desc: 'Female, energetic', lang: 'en-US' },
  { id: 'Polly.Ivy', name: 'Ivy', desc: 'Female, child voice', lang: 'en-US' },
  { id: 'Polly.Joey', name: 'Joey', desc: 'Male, casual & warm', lang: 'en-US' },
];

export default function SettingsPage({ useMock = false }) {
  const { user, axiosAuth, isAdmin, canViewAudit } = useAuth();
  const [activeTab, setActiveTab] = useState('voice');
  const [voiceModel, setVoiceModel] = useState('Polly.Joanna');
  const [retentionYears, setRetentionYears] = useState(7);
  const [autoArchive, setAutoArchive] = useState(false);
  const [auditLogs, setAuditLogs] = useState([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loadingLogs, setLoadingLogs] = useState(false);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    if (useMock) return;
    try {
      const api = axiosAuth();
      const [voiceRes, retentionRes] = await Promise.all([
        api.get('/settings/voice').catch(() => ({ data: { voice_model: 'Polly.Joanna' } })),
        api.get('/settings/data-retention').catch(() => ({ data: { retention_years: 7, auto_archive_enabled: false } }))
      ]);
      setVoiceModel(voiceRes.data.voice_model || 'Polly.Joanna');
      setRetentionYears(retentionRes.data.retention_years || 7);
      setAutoArchive(retentionRes.data.auto_archive_enabled || false);
    } catch (err) { console.error('Settings fetch error:', err); }
  };

  const fetchAuditLogs = async () => {
    setLoadingLogs(true);
    if (useMock) {
      setAuditLogs([
        { id: '1', action: 'patient_created', resource_type: 'patient', timestamp: '2025-07-15T10:00:00Z', details: { patient_name: 'Sarah Johnson' } },
        { id: '2', action: 'appointment_created', resource_type: 'appointment', timestamp: '2025-07-15T09:30:00Z', details: { patient_name: 'James Wilson' } },
        { id: '3', action: 'consent_captured', resource_type: 'patient', timestamp: '2025-07-14T14:00:00Z', details: { patient_name: 'Emily Chen' } },
      ]);
      setLoadingLogs(false);
      return;
    }
    try {
      const api = axiosAuth();
      const res = await api.get('/audit-logs?limit=20');
      setAuditLogs(res.data.logs || []);
    } catch { setAuditLogs([]); } finally { setLoadingLogs(false); }
  };

  const saveVoice = async () => {
    if (!isAdmin) {
      alert('Only administrators can modify voice settings');
      return;
    }
    setSaving(true);
    try {
      if (!useMock) {
        const api = axiosAuth();
        await api.post('/settings/voice', { voice_model: voiceModel });
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) { console.error('Save error:', err); } finally { setSaving(false); }
  };

  const saveRetention = async () => {
    if (!isAdmin) {
      alert('Only administrators can modify data retention policy');
      return;
    }
    setSaving(true);
    try {
      if (!useMock) {
        const api = axiosAuth();
        await api.post('/settings/data-retention', { retention_years: retentionYears, auto_archive_enabled: autoArchive });
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) { console.error('Save error:', err); } finally { setSaving(false); }
  };

  const formatTime = (ts) => {
    if (!ts) return '—';
    try { return new Date(ts).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }); } catch { return '—'; }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-1">Configure your AI receptionist</p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-white border border-gray-200">
          <TabsTrigger value="voice" className="gap-1.5"><Mic className="w-4 h-4" />Voice</TabsTrigger>
          <TabsTrigger value="retention" className="gap-1.5"><Database className="w-4 h-4" />Data Retention</TabsTrigger>
          <TabsTrigger value="audit" className="gap-1.5" onClick={fetchAuditLogs}><Shield className="w-4 h-4" />Audit Logs</TabsTrigger>
        </TabsList>

        <TabsContent value="voice" className="mt-4">
          <Card className="border-gray-200/80">
            <CardHeader>
              <CardTitle className="text-base">Voice Model</CardTitle>
              <CardDescription>Select the AI voice for phone calls</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {voiceModels.map(v => (
                  <button
                    key={v.id}
                    onClick={() => setVoiceModel(v.id)}
                    className={`p-3 rounded-lg border text-left transition-all ${
                      voiceModel === v.id
                        ? 'border-teal-300 bg-teal-50/50 ring-1 ring-teal-200'
                        : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-900">{v.name}</span>
                      {voiceModel === v.id && <CheckCircle2 className="w-4 h-4 text-teal-600" />}
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{v.desc}</p>
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-2 pt-2">
                <Button onClick={saveVoice} className="bg-teal-600 hover:bg-teal-700" disabled={saving || !isAdmin}>
                  {saving ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Save className="w-4 h-4 mr-1" />}
                  {saved ? 'Saved!' : 'Save'}
                </Button>
                {!isAdmin && <p className="text-xs text-amber-600">Admin access required to modify voice settings</p>}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="retention" className="mt-4">
          <Card className="border-gray-200/80">
            <CardHeader>
              <CardTitle className="text-base">Data Retention Policy</CardTitle>
              <CardDescription>Configure how long patient data is retained</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Retention Period (years)</Label>
                <div className="flex items-center gap-3">
                  <Input type="number" min={1} max={99} value={retentionYears} onChange={e => setRetentionYears(parseInt(e.target.value) || 7)} className="w-24" />
                  <span className="text-sm text-gray-500">years</span>
                </div>
                <p className="text-xs text-gray-400">Recommended: 7 years for dental records compliance</p>
              </div>
              <div className="flex items-center justify-between p-3 rounded-lg bg-gray-50">
                <div>
                  <p className="text-sm font-medium text-gray-700">Auto-Archive</p>
                  <p className="text-xs text-gray-500">Automatically archive records past retention period</p>
                </div>
                <Switch checked={autoArchive} onCheckedChange={setAutoArchive} />
              </div>
              <Button onClick={saveRetention} className="bg-teal-600 hover:bg-teal-700" disabled={saving || !isAdmin}>
                {saving ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <Save className="w-4 h-4 mr-1" />}
                {saved ? 'Saved!' : 'Save Policy'}
              </Button>
              {!isAdmin && <p className="text-xs text-amber-600 mt-2">Admin access required to modify data retention policy</p>}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="audit" className="mt-4">
          <Card className="border-gray-200/80">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base">Audit Logs</CardTitle>
                  <CardDescription>Track all actions for compliance</CardDescription>
                </div>
                <Button variant="outline" size="sm" onClick={fetchAuditLogs}>
                  <RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {loadingLogs ? (
                <div className="flex justify-center py-8"><div className="w-5 h-5 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" /></div>
              ) : auditLogs.length === 0 ? (
                <p className="text-sm text-gray-500 text-center py-8">No audit logs yet</p>
              ) : (
                <div className="space-y-2">
                  {auditLogs.map(log => (
                    <div key={log.id} className="flex items-center justify-between p-3 rounded-lg bg-gray-50/80 hover:bg-gray-100/80 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
                          <FileText className="w-4 h-4 text-gray-500" />
                        </div>
                        <div>
                          <p className="text-sm font-medium text-gray-900">{log.action.replace(/_/g, ' ')}</p>
                          <p className="text-xs text-gray-500">{log.details?.patient_name || log.resource_type}</p>
                        </div>
                      </div>
                      <span className="text-xs text-gray-400">{formatTime(log.timestamp)}</span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
