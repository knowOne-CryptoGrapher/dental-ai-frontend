import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  FileText, Search, CheckCircle2, Clock, XCircle, Plus,
  Shield, DollarSign, Loader2, AlertCircle
} from 'lucide-react';

export default function InsurancePage() {
  const { axiosAuth } = useAuth();
  const [tab, setTab] = useState('claims');
  const [claims, setClaims] = useState([]);
  const [carriers, setCarriers] = useState([]);
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [eligDialog, setEligDialog] = useState(false);
  const [claimDialog, setClaimDialog] = useState(false);
  const [eligResult, setEligResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [eligForm, setEligForm] = useState({ carrier: '', policy_number: '', patient_name: '', date_of_birth: '' });
  const [claimForm, setClaimForm] = useState({ patient_id: '', carrier: '', policy_number: '', procedures: [{ code: '', description: '', fee: '' }] });

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    try {
      const api = axiosAuth();
      const [claimsRes, carriersRes, patientsRes] = await Promise.all([
        api.get('/insurance/claims'),
        api.get('/insurance/carriers'),
        api.get('/patients'),
      ]);
      setClaims(claimsRes.data);
      setCarriers(carriersRes.data);
      setPatients(patientsRes.data || []);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  };

  const checkEligibility = async () => {
    setSubmitting(true);
    try {
      const api = axiosAuth();
      const res = await api.post('/insurance/eligibility', eligForm);
      setEligResult(res.data);
    } catch (e) { console.error(e); } finally { setSubmitting(false); }
  };

  const submitClaim = async () => {
    setSubmitting(true);
    try {
      const api = axiosAuth();
      const procs = claimForm.procedures.filter(p => p.code).map(p => ({ ...p, fee: parseFloat(p.fee) || 0 }));
      await api.post('/insurance/submit-claim', { ...claimForm, procedures: procs });
      setClaimDialog(false); await fetchData();
    } catch (e) { console.error(e); } finally { setSubmitting(false); }
  };

  const statusConfig = {
    draft: { color: 'bg-gray-100 text-gray-600', icon: Clock },
    submitted: { color: 'bg-blue-50 text-blue-700', icon: Clock },
    pending: { color: 'bg-amber-50 text-amber-700', icon: Clock },
    approved: { color: 'bg-emerald-50 text-emerald-700', icon: CheckCircle2 },
    denied: { color: 'bg-red-50 text-red-600', icon: XCircle },
    partial: { color: 'bg-amber-50 text-amber-700', icon: AlertCircle },
  };

  return (
    <div className="space-y-6 max-w-7xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Insurance</h1>
          <p className="text-sm text-gray-500 mt-1">ITRANS 2.0 + CDANet eligibility & claims</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => { setEligDialog(true); setEligResult(null); }}>
            <Shield className="w-4 h-4 mr-1" /> Check Eligibility
          </Button>
          <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => setClaimDialog(true)}>
            <Plus className="w-4 h-4 mr-1" /> Submit Claim
          </Button>
        </div>
      </div>

      {/* Claims List */}
      <Card className="border-gray-200/80">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Claims ({claims.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8"><div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" /></div>
          ) : claims.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-8">No claims submitted yet</p>
          ) : (
            <div className="space-y-2">
              {claims.map(claim => {
                const sc = statusConfig[claim.status] || statusConfig.draft;
                return (
                  <div key={claim.id} className="flex items-center justify-between p-3 rounded-lg bg-gray-50/80 hover:bg-gray-100/80 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-full bg-teal-100 flex items-center justify-center"><FileText className="w-4 h-4 text-teal-600" /></div>
                      <div>
                        <p className="text-sm font-medium text-gray-900">{claim.patient_name}</p>
                        <p className="text-xs text-gray-500">{claim.carrier_name || claim.carrier} · {claim.procedures?.length || 0} procedures · ${claim.total_amount?.toFixed(2)}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className={`text-[10px] ${sc.color}`}>{claim.status}</Badge>
                      <span className="text-xs text-gray-400">{claim.submission_method?.toUpperCase()}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Carriers */}
      <Card className="border-gray-200/80">
        <CardHeader className="pb-3"><CardTitle className="text-base">Supported Carriers</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
            {carriers.map(c => (
              <div key={c.id} className="p-3 rounded-lg border border-gray-200 text-center">
                <p className="text-sm font-medium text-gray-900">{c.name}</p>
                <p className="text-[10px] text-gray-400 uppercase mt-0.5">{c.method}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Eligibility Dialog */}
      <Dialog open={eligDialog} onOpenChange={setEligDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle>Check Eligibility</DialogTitle></DialogHeader>
          {eligResult ? (
            <div className="space-y-3">
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg">
                <p className="text-sm font-semibold text-emerald-800">Status: {eligResult.status}</p>
                <p className="text-xs text-emerald-600 mt-1">{eligResult.carrier_name} · {eligResult.policy_number}</p>
              </div>
              {eligResult.coverage && Object.entries(eligResult.coverage).map(([k, v]) => (
                <div key={k} className="flex justify-between text-sm p-2 bg-gray-50 rounded">
                  <span className="capitalize text-gray-600">{k}</span>
                  <span className="font-medium">{v.percentage}% · ${v.remaining || v.annual_max} remaining</span>
                </div>
              ))}
              <p className="text-[10px] text-amber-600 bg-amber-50 p-2 rounded">MOCKED RESPONSE — Connect ITRANS/CDANet for live data</p>
              <Button variant="outline" onClick={() => { setEligResult(null); setEligDialog(false); }} className="w-full">Close</Button>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label>Carrier</Label>
                <select value={eligForm.carrier} onChange={e => setEligForm({ ...eligForm, carrier: e.target.value })} className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm">
                  <option value="">Select carrier</option>
                  {carriers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
              <div className="space-y-1.5"><Label>Policy Number</Label><Input value={eligForm.policy_number} onChange={e => setEligForm({ ...eligForm, policy_number: e.target.value })} /></div>
              <div className="space-y-1.5"><Label>Patient Name</Label><Input value={eligForm.patient_name} onChange={e => setEligForm({ ...eligForm, patient_name: e.target.value })} /></div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setEligDialog(false)}>Cancel</Button>
                <Button className="bg-teal-600 hover:bg-teal-700" onClick={checkEligibility} disabled={submitting}>
                  {submitting && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Check
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Submit Claim Dialog */}
      <Dialog open={claimDialog} onOpenChange={setClaimDialog}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Submit Claim</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5">
              <Label>Carrier</Label>
              <select value={claimForm.carrier} onChange={e => setClaimForm({ ...claimForm, carrier: e.target.value })} className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm">
                <option value="">Select carrier</option>
                {carriers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5"><Label>Policy #</Label><Input data-testid="claim-policy-input" value={claimForm.policy_number} onChange={e => setClaimForm({ ...claimForm, policy_number: e.target.value })} /></div>
              <div className="space-y-1.5">
                <Label>Patient</Label>
                <select
                  data-testid="claim-patient-select"
                  value={claimForm.patient_id}
                  onChange={e => setClaimForm({ ...claimForm, patient_id: e.target.value })}
                  className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm"
                >
                  <option value="">Select patient</option>
                  {patients.map(p => (
                    <option key={p.id} value={p.id}>{p.name}{p.phone ? ` · ${p.phone}` : ''}</option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <Label>Procedures</Label>
              {claimForm.procedures.map((p, i) => (
                <div key={i} className="grid grid-cols-3 gap-1.5 mt-1.5">
                  <Input placeholder="Code" value={p.code} onChange={e => { const procs = [...claimForm.procedures]; procs[i].code = e.target.value; setClaimForm({ ...claimForm, procedures: procs }); }} />
                  <Input placeholder="Description" value={p.description} onChange={e => { const procs = [...claimForm.procedures]; procs[i].description = e.target.value; setClaimForm({ ...claimForm, procedures: procs }); }} />
                  <Input placeholder="Fee" type="number" value={p.fee} onChange={e => { const procs = [...claimForm.procedures]; procs[i].fee = e.target.value; setClaimForm({ ...claimForm, procedures: procs }); }} />
                </div>
              ))}
              <Button variant="ghost" size="sm" className="mt-1 text-xs" onClick={() => setClaimForm({ ...claimForm, procedures: [...claimForm.procedures, { code: '', description: '', fee: '' }] })}>+ Add Procedure</Button>
            </div>
            <p className="text-[10px] text-amber-600 bg-amber-50 p-2 rounded">MOCKED — Claims are simulated. Connect ITRANS/CDANet for live submission.</p>
            <DialogFooter>
              <Button variant="outline" onClick={() => setClaimDialog(false)}>Cancel</Button>
              <Button data-testid="claim-submit-btn" className="bg-teal-600 hover:bg-teal-700" onClick={submitClaim} disabled={submitting || !claimForm.patient_id || !claimForm.carrier}>
                {submitting && <Loader2 className="w-4 h-4 mr-1 animate-spin" />} Submit
              </Button>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
