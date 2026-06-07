import React, { useState, useEffect } from 'react';
import { useFeatures } from '../hooks/useFeatures';
import FeatureUpgradeCard from '../components/FeatureUpgradeCard';
import { api } from '../config/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';

const STATUS_STYLE = {
  pending:   'bg-amber-50   text-amber-700   border-amber-200',
  submitted: 'bg-blue-50    text-blue-700    border-blue-200',
  accepted:  'bg-emerald-50 text-emerald-700 border-emerald-200',
  rejected:  'bg-red-50     text-red-600     border-red-200',
  error:     'bg-red-50     text-red-600     border-red-200',
};

const INITIAL_FORM = {
  patient_id:     '',
  provider_id:    '',
  service_date:   '',
  procedure_code: '',
  fee:            '',
  carrier_id:     '',
  tooth_code:     '',
  diagnosis_code: '',
};

function fmtDate(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString('en-CA'); }
  catch { return iso; }
}

export default function ClaimsPage() {
  const { has, featuresLoading } = useFeatures();

  const [claims, setClaims]             = useState([]);
  const [claimsLoading, setClaimsLoading] = useState(true);

  const [form, setForm]           = useState(INITIAL_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg]     = useState('');

  useEffect(() => {
    if (featuresLoading || !has('insurance')) return;
    fetchClaims();
  }, [featuresLoading]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchClaims = async () => {
    setClaimsLoading(true);
    try {
      const res = await api.get('/claims');
      setClaims(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setClaimsLoading(false);
    }
  };

  const set = (key) => (e) => setForm(f => ({ ...f, [key]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setSuccessMsg('');
    setErrorMsg('');
    try {
      const payload = {
        patient_id:      form.patient_id,
        provider_id:     form.provider_id,
        service_date:    form.service_date,
        procedure_codes: [form.procedure_code],
        fee:             parseFloat(form.fee),
        ...(form.carrier_id     && { carrier_id:     form.carrier_id }),
        ...(form.tooth_code     && { tooth_code:     form.tooth_code }),
        ...(form.diagnosis_code && { diagnosis_code: form.diagnosis_code }),
      };
      await api.post('/claims/submit', payload);
      setSuccessMsg(
        'Claim submitted — pending CDAnet certification. ' +
        'Your claim has been queued and will be transmitted once ITRANS integration is active.'
      );
      setForm(INITIAL_FORM);
      fetchClaims();
    } catch (err) {
      setErrorMsg(
        err.response?.data?.detail ||
        'Failed to submit claim. Please try again.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (!featuresLoading && !has('insurance')) {
    return (
      <FeatureUpgradeCard
        featureName="Insurance Claims"
        description="Submit and track CDAnet dental insurance claims directly from Dental AI."
        bullets={[
          'CDAnet claim submission',
          'Real-time claim status tracking',
          'ITRANS 2.0 integration',
          'Claim history and audit trail',
        ]}
        requiredTier="Professional"
        ctaLabel="Upgrade to Professional"
      />
    );
  }

  const canSubmit =
    form.patient_id && form.provider_id && form.service_date &&
    form.procedure_code && form.fee && !submitting;

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Claims</h1>
        <p className="text-sm text-gray-500 mt-1">CDAnet claim submission via ITRANS 2.0</p>
      </div>

      {/* ── Submit a Claim ──────────────────────────────────────────── */}
      <Card className="border-gray-200/80">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Submit a Claim</CardTitle>
        </CardHeader>

        <CardContent>
          {successMsg && (
            <div className="flex items-start gap-2 p-3 mb-4 rounded-lg bg-emerald-50 border border-emerald-200">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" aria-hidden="true" />
              <p className="text-sm text-emerald-700">{successMsg}</p>
            </div>
          )}

          {errorMsg && (
            <div className="flex items-start gap-2 p-3 mb-4 rounded-lg bg-red-50 border border-red-200">
              <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" aria-hidden="true" />
              <p className="text-sm text-red-600">{errorMsg}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Required fields */}
              <div className="space-y-1.5">
                <Label htmlFor="patient_id">
                  Patient ID <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="patient_id"
                  value={form.patient_id}
                  onChange={set('patient_id')}
                  placeholder="patient-uuid"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="provider_id">
                  Provider ID <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="provider_id"
                  value={form.provider_id}
                  onChange={set('provider_id')}
                  placeholder="provider-uuid"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="service_date">
                  Service Date <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="service_date"
                  type="date"
                  value={form.service_date}
                  onChange={set('service_date')}
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="procedure_code">
                  Procedure Code <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="procedure_code"
                  value={form.procedure_code}
                  onChange={set('procedure_code')}
                  placeholder="e.g. 11101"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="fee">
                  Fee (CAD) <span className="text-red-500">*</span>
                </Label>
                <Input
                  id="fee"
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.fee}
                  onChange={set('fee')}
                  placeholder="0.00"
                  required
                />
              </div>

              {/* Optional fields */}
              <div className="space-y-1.5">
                <Label htmlFor="carrier_id">
                  Carrier ID{' '}
                  <span className="text-gray-400 text-xs font-normal">(optional)</span>
                </Label>
                <Input
                  id="carrier_id"
                  value={form.carrier_id}
                  onChange={set('carrier_id')}
                  placeholder="carrier code"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="tooth_code">
                  Tooth Code{' '}
                  <span className="text-gray-400 text-xs font-normal">(optional)</span>
                </Label>
                <Input
                  id="tooth_code"
                  value={form.tooth_code}
                  onChange={set('tooth_code')}
                  placeholder="e.g. 11"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="diagnosis_code">
                  Diagnosis Code{' '}
                  <span className="text-gray-400 text-xs font-normal">(optional)</span>
                </Label>
                <Input
                  id="diagnosis_code"
                  value={form.diagnosis_code}
                  onChange={set('diagnosis_code')}
                  placeholder="ICD-10 code"
                />
              </div>
            </div>

            <div className="pt-1">
              <p className="text-[11px] text-amber-600 bg-amber-50 px-3 py-2 rounded-lg mb-3">
                ITRANS certification pending — claims will be queued for transmission once
                vendor credentials are active.
              </p>
              <Button
                type="submit"
                disabled={!canSubmit}
                className="bg-teal-600 hover:bg-teal-700"
              >
                {submitting && (
                  <Loader2 className="w-4 h-4 mr-1.5 animate-spin" aria-hidden="true" />
                )}
                Submit Claim
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* ── Claims History ──────────────────────────────────────────── */}
      <Card className="border-gray-200/80">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Claims History</CardTitle>
        </CardHeader>

        <CardContent>
          {claimsLoading ? (
            <div className="flex justify-center py-8">
              <div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : claims.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-8">No claims submitted yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100">
                    {['Claim ID', 'Patient', 'Provider', 'Service Date', 'Status', 'Created'].map(h => (
                      <th
                        key={h}
                        className="text-left text-xs font-semibold text-gray-500 uppercase tracking-wide pb-2 pr-4 last:pr-0"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {claims.map(claim => (
                    <tr key={claim.id} className="hover:bg-gray-50/60 transition-colors">
                      <td className="py-2.5 pr-4 font-mono text-xs text-gray-600 whitespace-nowrap">
                        {claim.id?.slice(0, 8)}…
                      </td>
                      <td className="py-2.5 pr-4 text-gray-700 max-w-[100px] truncate">
                        {claim.patient_id?.slice(0, 8)}…
                      </td>
                      <td className="py-2.5 pr-4 text-gray-700 max-w-[100px] truncate">
                        {claim.provider_id?.slice(0, 8)}…
                      </td>
                      <td className="py-2.5 pr-4 text-gray-600 whitespace-nowrap">
                        {claim.service_date || '—'}
                      </td>
                      <td className="py-2.5 pr-4">
                        <Badge
                          variant="outline"
                          className={`text-[10px] ${STATUS_STYLE[claim.status] ?? STATUS_STYLE.pending}`}
                        >
                          {claim.status}
                        </Badge>
                      </td>
                      <td className="py-2.5 text-gray-500 text-xs whitespace-nowrap">
                        {fmtDate(claim.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
