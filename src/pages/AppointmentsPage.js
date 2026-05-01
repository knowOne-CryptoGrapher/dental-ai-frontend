import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Calendar, Clock, CheckCircle2, XCircle, AlertTriangle,
  Filter, Search, Loader2, ShieldCheck
} from 'lucide-react';
import { mockAppointments } from '../data/mockData';

export default function AppointmentsPage({ useMock = false }) {
  const { axiosAuth } = useAuth();
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [verifyDialog, setVerifyDialog] = useState(null);
  const [verifying, setVerifying] = useState(false);

  useEffect(() => { fetchAppointments(); }, []);

  const fetchAppointments = async () => {
    if (useMock) { setAppointments(mockAppointments); setLoading(false); return; }
    try {
      const api = axiosAuth();
      const res = await api.get('/appointments');
      setAppointments(res.data);
    } catch { setAppointments(mockAppointments); } finally { setLoading(false); }
  };

  const handleVerify = async (appointmentId) => {
    setVerifying(true);
    try {
      if (useMock) {
        setAppointments(prev => prev.map(a => a.id === appointmentId ? { ...a, status: 'scheduled' } : a));
      } else {
        const api = axiosAuth();
        await api.post(`/appointments/${appointmentId}/verify`, { verified_by: 'staff' });
        await fetchAppointments();
      }
      setVerifyDialog(null);
    } catch (err) { console.error('Verify failed:', err); } finally { setVerifying(false); }
  };

  const handleCancel = async (appointmentId) => {
    if (!window.confirm('Cancel this appointment?')) return;
    try {
      if (useMock) {
        setAppointments(prev => prev.map(a => a.id === appointmentId ? { ...a, status: 'cancelled' } : a));
      } else {
        const api = axiosAuth();
        const response = await api.delete(`/appointments/${appointmentId}`);
        console.log('Cancel response:', response.data);
        await fetchAppointments();
        alert('Appointment cancelled successfully');
      }
    } catch (err) { 
      console.error('Cancel failed:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Failed to cancel appointment';
      alert(`Error: ${errorMsg}`);
    }
  };

  const statusConfig = {
    scheduled: { label: 'Scheduled', className: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: CheckCircle2 },
    pending_verification: { label: 'Pending', className: 'bg-amber-50 text-amber-700 border-amber-200', icon: Clock },
    completed: { label: 'Completed', className: 'bg-gray-100 text-gray-600 border-gray-200', icon: CheckCircle2 },
    cancelled: { label: 'Cancelled', className: 'bg-red-50 text-red-600 border-red-200', icon: XCircle },
  };

  const filters = [
    { value: 'all', label: 'All' },
    { value: 'pending_verification', label: 'Pending' },
    { value: 'scheduled', label: 'Scheduled' },
    { value: 'completed', label: 'Completed' },
    { value: 'cancelled', label: 'Cancelled' },
  ];

  const filtered = appointments
    .filter(a => filter === 'all' || a.status === filter)
    .filter(a =>
      a.patient_name?.toLowerCase().includes(search.toLowerCase()) ||
      a.service_type?.toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => {
      if (a.status === 'pending_verification' && b.status !== 'pending_verification') return -1;
      if (b.status === 'pending_verification' && a.status !== 'pending_verification') return 1;
      return new Date(a.appointment_date) - new Date(b.appointment_date);
    });

  const pendingCount = appointments.filter(a => a.status === 'pending_verification').length;

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Appointments</h1>
        <p className="text-sm text-gray-500 mt-1">{appointments.length} total appointments{pendingCount > 0 && ` · ${pendingCount} pending verification`}</p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center bg-white rounded-lg border border-gray-200 p-0.5 gap-0.5">
          {filters.map(f => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                filter === f.value ? 'bg-teal-50 text-teal-700' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)} className="pl-9 h-9 w-48" />
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : (
        <div className="space-y-3">
          {filtered.map((apt) => {
            const sc = statusConfig[apt.status] || statusConfig.scheduled;
            const StatusIcon = sc.icon;
            return (
              <Card key={apt.id} className={`border-gray-200/80 transition-all hover:shadow-sm ${apt.status === 'pending_verification' ? 'border-l-4 border-l-amber-400' : ''} ${apt.is_emergency ? 'ring-1 ring-red-200' : ''}`}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between flex-wrap gap-3">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-full bg-teal-100 flex items-center justify-center shrink-0">
                        <span className="text-sm font-semibold text-teal-700">{apt.patient_name?.charAt(0)}</span>
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold text-gray-900">{apt.patient_name}</p>
                          {apt.is_emergency && <Badge variant="destructive" className="text-[10px]">EMERGENCY</Badge>}
                        </div>
                        <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
                          <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{apt.appointment_date}</span>
                          <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{apt.appointment_time}</span>
                          <span className="text-gray-400">·</span>
                          <span>{apt.service_type}</span>
                          {apt.provider_name && (
                            <>
                              <span className="text-gray-400">·</span>
                              <span className="font-medium text-teal-600">{apt.provider_name}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" className={`text-xs ${sc.className}`}>
                        <StatusIcon className="w-3 h-3 mr-1" />{sc.label}
                      </Badge>
                      {apt.status === 'pending_verification' && (
                        <Button size="sm" className="bg-teal-600 hover:bg-teal-700 h-8" onClick={() => setVerifyDialog(apt)}>
                          <ShieldCheck className="w-3.5 h-3.5 mr-1" /> Verify
                        </Button>
                      )}
                      {apt.status !== 'cancelled' && apt.status !== 'completed' && (
                        <Button size="sm" variant="ghost" className="h-8 text-red-500 hover:text-red-600 hover:bg-red-50" onClick={() => handleCancel(apt.id)}>
                          <XCircle className="w-3.5 h-3.5 mr-1" /> Cancel
                        </Button>
                      )}
                    </div>
                  </div>
                  {apt.notes && <p className="text-xs text-gray-500 mt-2 ml-14">{apt.notes}</p>}
                </CardContent>
              </Card>
            );
          })}
          {filtered.length === 0 && <p className="text-sm text-gray-500 text-center py-12">No appointments found</p>}
        </div>
      )}

      {/* Verify Dialog */}
      <Dialog open={!!verifyDialog} onOpenChange={() => setVerifyDialog(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Verify Appointment</DialogTitle>
          </DialogHeader>
          {verifyDialog && (
            <div className="space-y-3">
              <div className="p-3 bg-gray-50 rounded-lg space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-gray-500">Patient</span><span className="font-medium">{verifyDialog.patient_name}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">Date</span><span className="font-medium">{verifyDialog.appointment_date}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">Time</span><span className="font-medium">{verifyDialog.appointment_time}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">Service</span><span className="font-medium">{verifyDialog.service_type}</span></div>
              </div>
              {verifyDialog.is_emergency && (
                <div className="p-2 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-500" />
                  <span className="text-xs text-red-700 font-medium">This is marked as an emergency appointment</span>
                </div>
              )}
              <DialogFooter>
                <Button variant="outline" onClick={() => setVerifyDialog(null)}>Cancel</Button>
                <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => handleVerify(verifyDialog.id)} disabled={verifying}>
                  {verifying && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
                  Confirm & Schedule
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
