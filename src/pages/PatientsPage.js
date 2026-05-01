import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import {
  Search, Plus, Phone, Mail, FileText, Edit2, Trash2,
  User, ChevronDown, X, Loader2, AlertCircle
} from 'lucide-react';
import { mockPatients } from '../data/mockData';

export default function PatientsPage({ useMock = false }) {
  const { axiosAuth, isAdmin } = useAuth();
  const [patients, setPatients] = useState([]);
  const [search, setSearch] = useState('');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingPatient, setEditingPatient] = useState(null);
  const [detailPatient, setDetailPatient] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    name: '', phone: '', email: '', date_of_birth: '',
    preferred_contact: 'phone', emergency_contact_name: '',
    emergency_contact_phone: '', emergency_contact_relationship: '', notes: ''
  });

  useEffect(() => {
    fetchPatients();
  }, []);

  const fetchPatients = async () => {
    if (useMock) {
      setPatients(mockPatients);
      setLoading(false);
      return;
    }
    try {
      const api = axiosAuth();
      const res = await api.get('/patients');
      setPatients(res.data);
    } catch (err) {
      setPatients(mockPatients);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    try {
      if (useMock) {
        if (editingPatient) {
          setPatients(prev => prev.map(p => p.id === editingPatient.id ? { ...p, ...form } : p));
        } else {
          const newPatient = { ...form, id: Date.now().toString(), file_number: `DP-NEW-${Date.now()}`, created_at: new Date().toISOString(), consent_given: false };
          setPatients(prev => [newPatient, ...prev]);
        }
      } else {
        const api = axiosAuth();
        if (editingPatient) {
          await api.put(`/patients/${editingPatient.id}`, form);
        } else {
          await api.post('/patients', form);
        }
        await fetchPatients();
      }
      closeDialog();
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : detail?.message || 'Failed to save patient');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this patient?')) return;
    try {
      if (useMock) {
        setPatients(prev => prev.filter(p => p.id !== id));
      } else {
        const api = axiosAuth();
        await api.delete(`/patients/${id}`);
        await fetchPatients();
      }
      setDetailPatient(null);
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const openEdit = (patient) => {
    setEditingPatient(patient);
    setForm({
      name: patient.name, phone: patient.phone, email: patient.email || '',
      date_of_birth: patient.date_of_birth || '', preferred_contact: patient.preferred_contact || 'phone',
      emergency_contact_name: patient.emergency_contact_name || '',
      emergency_contact_phone: patient.emergency_contact_phone || '',
      emergency_contact_relationship: patient.emergency_contact_relationship || '',
      notes: patient.notes || ''
    });
    setDialogOpen(true);
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setEditingPatient(null);
    setError('');
    setForm({ name: '', phone: '', email: '', date_of_birth: '', preferred_contact: 'phone', emergency_contact_name: '', emergency_contact_phone: '', emergency_contact_relationship: '', notes: '' });
  };

  const filtered = patients.filter(p =>
    p.name?.toLowerCase().includes(search.toLowerCase()) ||
    p.phone?.includes(search) ||
    p.email?.toLowerCase().includes(search.toLowerCase()) ||
    p.file_number?.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-6 max-w-7xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Patients</h1>
          <p className="text-sm text-gray-500 mt-1">{patients.length} total patients</p>
        </div>
        <Button onClick={() => setDialogOpen(true)} className="bg-teal-600 hover:bg-teal-700">
          <Plus className="w-4 h-4 mr-2" /> Add Patient
        </Button>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <Input placeholder="Search patients..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-10" />
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-32"><div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : (
        <div className="grid gap-3">
          {/* Table header */}
          <div className="hidden md:grid grid-cols-12 gap-4 px-4 py-2 text-xs font-medium text-gray-500 uppercase tracking-wide">
            <div className="col-span-1">File #</div>
            <div className="col-span-3">Name</div>
            <div className="col-span-2">Phone</div>
            <div className="col-span-2">Email</div>
            <div className="col-span-2">Consent</div>
            <div className="col-span-2 text-right">Actions</div>
          </div>
          {filtered.map((patient) => (
            <Card key={patient.id} className="border-gray-200/80 hover:shadow-sm transition-shadow cursor-pointer" onClick={() => setDetailPatient(patient)}>
              <CardContent className="p-4">
                <div className="md:grid md:grid-cols-12 md:gap-4 md:items-center space-y-2 md:space-y-0">
                  <div className="col-span-1 text-xs font-mono text-gray-400">{patient.file_number?.split('-').pop()}</div>
                  <div className="col-span-3 flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-teal-100 flex items-center justify-center shrink-0">
                      <span className="text-xs font-semibold text-teal-700">{patient.name?.charAt(0)}</span>
                    </div>
                    <span className="text-sm font-medium text-gray-900">{patient.name}</span>
                  </div>
                  <div className="col-span-2 text-sm text-gray-600">{patient.phone}</div>
                  <div className="col-span-2 text-sm text-gray-600 truncate">{patient.email || '—'}</div>
                  <div className="col-span-2">
                    <Badge variant="outline" className={patient.consent_given ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-amber-200 bg-amber-50 text-amber-700'}>
                      {patient.consent_given ? 'Given' : 'Pending'}
                    </Badge>
                  </div>
                  <div className="col-span-2 flex items-center justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEdit(patient)}><Edit2 className="w-3.5 h-3.5 text-gray-500" /></Button>
                    {isAdmin && <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleDelete(patient.id)}><Trash2 className="w-3.5 h-3.5 text-red-500" /></Button>}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
          {filtered.length === 0 && <p className="text-sm text-gray-500 text-center py-12">No patients found</p>}
        </div>
      )}

      {/* Add/Edit Patient Dialog */}
      <Dialog open={dialogOpen} onOpenChange={closeDialog}>
        <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingPatient ? 'Edit Patient' : 'New Patient'}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2 space-y-1.5"><Label>Full Name *</Label><Input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required /></div>
              <div className="space-y-1.5"><Label>Phone *</Label><Input value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} required /></div>
              <div className="space-y-1.5"><Label>Email</Label><Input type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} /></div>
              <div className="space-y-1.5"><Label>Date of Birth</Label><Input type="date" value={form.date_of_birth} onChange={e => setForm({ ...form, date_of_birth: e.target.value })} /></div>
              <div className="space-y-1.5">
                <Label>Preferred Contact</Label>
                <select value={form.preferred_contact} onChange={e => setForm({ ...form, preferred_contact: e.target.value })} className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm">
                  <option value="phone">Phone</option>
                  <option value="email">Email</option>
                  <option value="sms">SMS</option>
                </select>
              </div>
            </div>
            <div className="border-t border-gray-100 pt-3">
              <p className="text-xs font-medium text-gray-500 mb-2">Emergency Contact</p>
              <div className="grid grid-cols-3 gap-2">
                <Input placeholder="Name" value={form.emergency_contact_name} onChange={e => setForm({ ...form, emergency_contact_name: e.target.value })} />
                <Input placeholder="Phone" value={form.emergency_contact_phone} onChange={e => setForm({ ...form, emergency_contact_phone: e.target.value })} />
                <Input placeholder="Relation" value={form.emergency_contact_relationship} onChange={e => setForm({ ...form, emergency_contact_relationship: e.target.value })} />
              </div>
            </div>
            <div className="space-y-1.5"><Label>Notes</Label><textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} rows={2} className="w-full rounded-md border border-gray-200 bg-white px-3 py-2 text-sm" /></div>
            {error && <div className="p-2 rounded bg-red-50 border border-red-200 text-xs text-red-600 flex items-center gap-1"><AlertCircle className="w-3 h-3" />{error}</div>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={closeDialog}>Cancel</Button>
              <Button type="submit" className="bg-teal-600 hover:bg-teal-700" disabled={saving}>
                {saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
                {editingPatient ? 'Update' : 'Create'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Patient Detail Dialog */}
      <Dialog open={!!detailPatient} onOpenChange={() => setDetailPatient(null)}>
        <DialogContent className="max-w-lg">
          {detailPatient && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-teal-100 flex items-center justify-center">
                    <span className="text-sm font-bold text-teal-700">{detailPatient.name?.charAt(0)}</span>
                  </div>
                  <div>
                    <p>{detailPatient.name}</p>
                    <p className="text-xs font-normal text-gray-500">{detailPatient.file_number}</p>
                  </div>
                </DialogTitle>
              </DialogHeader>
              <div className="space-y-3 mt-2">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div><p className="text-xs text-gray-500">Phone</p><p className="font-medium">{detailPatient.phone}</p></div>
                  <div><p className="text-xs text-gray-500">Email</p><p className="font-medium">{detailPatient.email || '—'}</p></div>
                  <div><p className="text-xs text-gray-500">Date of Birth</p><p className="font-medium">{detailPatient.date_of_birth || '—'}</p></div>
                  <div><p className="text-xs text-gray-500">Preferred Contact</p><p className="font-medium capitalize">{detailPatient.preferred_contact}</p></div>
                </div>
                {detailPatient.emergency_contact_name && (
                  <div className="p-3 rounded-lg bg-red-50/50 border border-red-100">
                    <p className="text-xs font-medium text-red-700 mb-1">Emergency Contact</p>
                    <p className="text-sm">{detailPatient.emergency_contact_name} ({detailPatient.emergency_contact_relationship}) — {detailPatient.emergency_contact_phone}</p>
                  </div>
                )}
                {detailPatient.notes && <div><p className="text-xs text-gray-500 mb-1">Notes</p><p className="text-sm text-gray-700 bg-gray-50 p-2 rounded">{detailPatient.notes}</p></div>}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
