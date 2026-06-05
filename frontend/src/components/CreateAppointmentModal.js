import React, { useState, useEffect } from 'react';
import { toast } from './ui/sonner';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../config/api';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Loader2 } from 'lucide-react';

const DEFAULT_TIMES = [
  '08:00','08:30','09:00','09:30','10:00','10:30','11:00','11:30',
  '12:00','12:30','13:00','13:30','14:00','14:30','15:00','15:30',
  '16:00','16:30','17:00','17:30','18:00',
];

function todayISO() {
  const d = new Date();
  return [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, '0'),
    String(d.getDate()).padStart(2, '0'),
  ].join('-');
}

export default function CreateAppointmentModal({ open, onClose, onCreated }) {
  const { user, practice } = useAuth();

  const [form, setForm] = useState({
    full_name: '',
    phone: '',
    email: '',
    appointment_type: '',
    date: todayISO(),
    time: '09:00',
    provider_id: '',
    notes: '',
  });
  const [providers, setProviders] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const appointmentTypes = practice?.settings?.appointment_types || [];

  useEffect(() => {
    if (!open) return;
    // Reset form when modal opens
    setForm({
      full_name: '', phone: '', email: '',
      appointment_type: appointmentTypes[0]?.id || '',
      date: todayISO(), time: '09:00',
      provider_id: '', notes: '',
    });
    setError('');
    // Load providers
    api.get('/providers').then(r => setProviders(r.data || [])).catch(() => {});
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const validate = () => {
    if (!form.full_name.trim()) return 'Patient name is required.';
    if (!form.phone.trim()) return 'Phone number is required.';
    if (!form.appointment_type) return 'Appointment type is required.';
    if (!form.date) return 'Date is required.';
    if (!form.time) return 'Time is required.';
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const msg = validate();
    if (msg) { setError(msg); return; }
    setError('');
    setSaving(true);

    const practiceId = user?.practice_id;
    if (!practiceId) {
      setError('Practice ID not available.');
      setSaving(false);
      return;
    }

    try {
      const payload = {
        full_name: form.full_name.trim(),
        phone: form.phone.trim(),
        email: form.email.trim() || undefined,
        appointment_type: form.appointment_type,
        date: form.date,
        time: form.time,
        provider_id: form.provider_id || undefined,
        notes: form.notes.trim() || undefined,
      };
      const res = await api.post(`/practices/${practiceId}/appointments`, payload);
      toast.success('Appointment created');
      onCreated?.(res.data);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create appointment. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Create Appointment</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-1">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
              {error}
            </div>
          )}

          {/* Patient info */}
          <div className="space-y-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
              Patient Information
            </p>
            <div className="space-y-1.5">
              <Label htmlFor="ca-fullname">Full Name *</Label>
              <Input
                id="ca-fullname"
                value={form.full_name}
                onChange={e => set('full_name', e.target.value)}
                placeholder="Jane Smith"
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="ca-phone">Phone *</Label>
                <Input
                  id="ca-phone"
                  type="tel"
                  value={form.phone}
                  onChange={e => set('phone', e.target.value)}
                  placeholder="(416) 555-0100"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="ca-email">Email</Label>
                <Input
                  id="ca-email"
                  type="email"
                  value={form.email}
                  onChange={e => set('email', e.target.value)}
                  placeholder="jane@example.com"
                />
              </div>
            </div>
          </div>

          {/* Appointment details */}
          <div className="space-y-3 pt-1 border-t border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide pt-1">
              Appointment Details
            </p>

            <div className="space-y-1.5">
              <Label htmlFor="ca-type">Appointment Type *</Label>
              <select
                id="ca-type"
                value={form.appointment_type}
                onChange={e => set('appointment_type', e.target.value)}
                className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm"
                required
              >
                <option value="">Select type…</option>
                {appointmentTypes.map(t => (
                  <option key={t.id} value={t.id}>
                    {t.name}{t.duration_min ? ` (${t.duration_min} min)` : ''}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="ca-date">Date *</Label>
                <Input
                  id="ca-date"
                  type="date"
                  value={form.date}
                  onChange={e => set('date', e.target.value)}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="ca-time">Time *</Label>
                <select
                  id="ca-time"
                  value={form.time}
                  onChange={e => set('time', e.target.value)}
                  className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm"
                  required
                >
                  {DEFAULT_TIMES.map(t => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="ca-provider">Provider</Label>
              <select
                id="ca-provider"
                value={form.provider_id}
                onChange={e => set('provider_id', e.target.value)}
                className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm"
              >
                <option value="">No specific provider</option>
                {providers
                  .filter(p => p.is_active !== false)
                  .map(p => (
                    <option key={p.id} value={p.id}>{p.name}</option>
                  ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="ca-notes">Notes</Label>
              <textarea
                id="ca-notes"
                value={form.notes}
                onChange={e => set('notes', e.target.value)}
                placeholder="Any additional information…"
                rows={3}
                className="w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={saving}>
              Cancel
            </Button>
            <Button
              type="submit"
              className="bg-teal-600 hover:bg-teal-700"
              disabled={saving}
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                  Creating…
                </>
              ) : 'Create Appointment'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
