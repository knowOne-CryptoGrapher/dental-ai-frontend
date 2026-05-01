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
  Calendar as CalendarIcon, ChevronLeft, ChevronRight, Clock, MapPin, User, Filter, Search, Plus, X
} from 'lucide-react';

export default function CalendarPage() {
  const { axiosAuth, user } = useAuth();
  const [view, setView] = useState('week'); // 'month' | 'week' | 'day'
  const [currentDate, setCurrentDate] = useState(new Date());
  const [appointments, setAppointments] = useState([]);
  const [providers, setProviders] = useState([]);
  const [locations, setLocations] = useState([]);
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [selectedAppointment, setSelectedAppointment] = useState(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showDetailsDialog, setShowDetailsDialog] = useState(false);
  const [filters, setFilters] = useState({
    provider: 'all',
    location: 'all',
    status: 'all',
    search: ''
  });
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [availableProviders, setAvailableProviders] = useState([]);
  const [checkingAvailability, setCheckingAvailability] = useState(false);

  useEffect(() => {
    fetchData();
  }, [currentDate]);

  const fetchData = async () => {
    try {
      const api = axiosAuth();
      const [aptsRes, provsRes, locsRes, patsRes] = await Promise.all([
        api.get('/appointments'),
        api.get('/providers'),
        api.get('/locations'),
        api.get('/patients')
      ]);
      setAppointments(aptsRes.data || []);
      setProviders(provsRes.data || []);
      setLocations(locsRes.data || []);
      setPatients(patsRes.data || []);
    } catch (e) {
      console.error('Failed to fetch calendar data:', e);
    } finally {
      setLoading(false);
    }
  };

  const getWeekDays = (date) => {
    const week = [];
    const startOfWeek = new Date(date);
    startOfWeek.setDate(date.getDate() - date.getDay()); // Start on Sunday
    
    for (let i = 0; i < 7; i++) {
      const day = new Date(startOfWeek);
      day.setDate(startOfWeek.getDate() + i);
      week.push(day);
    }
    return week;
  };

  const getMonthDays = (date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startDate = new Date(firstDay);
    startDate.setDate(firstDay.getDate() - firstDay.getDay());
    
    const days = [];
    const current = new Date(startDate);
    
    while (current <= lastDay || days.length < 35) {
      days.push(new Date(current));
      current.setDate(current.getDate() + 1);
    }
    return days;
  };

  const getTimeSlots = () => {
    const slots = [];
    for (let hour = 8; hour < 18; hour++) {
      slots.push(`${hour.toString().padStart(2, '0')}:00`);
      slots.push(`${hour.toString().padStart(2, '0')}:30`);
    }
    return slots;
  };

  const getAppointmentsForDate = (date) => {
    const dateStr = date.toISOString().split('T')[0];
    return appointments.filter(apt => {
      const aptDate = apt.appointment_date;
      if (filters.provider !== 'all' && apt.provider_id !== filters.provider) return false;
      if (filters.location !== 'all' && apt.location_id !== filters.location) return false;
      if (filters.status !== 'all' && apt.status !== filters.status) return false;
      if (filters.search && !apt.patient_name?.toLowerCase().includes(filters.search.toLowerCase())) return false;
      return aptDate === dateStr;
    });
  };

  const getAppointmentAtTime = (date, time) => {
    const dateStr = date.toISOString().split('T')[0];
    return appointments.find(apt => 
      apt.appointment_date === dateStr && 
      apt.appointment_time === time &&
      (filters.provider === 'all' || apt.provider_id === filters.provider) &&
      (filters.location === 'all' || apt.location_id === filters.location) &&
      (filters.status === 'all' || apt.status === filters.status)
    );
  };

  const handleSlotClick = async (date, time) => {
    const existing = getAppointmentAtTime(date, time);
    if (existing) {
      setSelectedAppointment(existing);
      setShowDetailsDialog(true);
    } else {
      const dateStr = date.toISOString().split('T')[0];
      setSelectedSlot({ date, time });
      
      // Prepare form with selected date/time
      const initialForm = {
        patient_id: '',
        patient_name: '',
        patient_phone: '',
        appointment_date: dateStr,
        appointment_time: time,
        service_type: 'Cleaning',
        provider_id: filters.provider !== 'all' ? filters.provider : '',
        location_id: filters.location !== 'all' ? filters.location : '',
        notes: ''
      };
      setForm(initialForm);
      
      // Fetch available providers for this slot
      if (initialForm.location_id) {
        setCheckingAvailability(true);
        try {
          const api = axiosAuth();
          const response = await api.post('/appointments/route', {
            appointment_type: initialForm.service_type,
            location_id: initialForm.location_id,
            date: dateStr,
            is_emergency: false
          });
          setAvailableProviders(response.data.providers || []);
          
          // Auto-select recommended provider if available
          if (response.data.recommended_provider_id) {
            setForm(prev => ({ ...prev, provider_id: response.data.recommended_provider_id }));
          }
        } catch (e) {
          console.error('Failed to fetch available providers:', e);
          setAvailableProviders([]);
        } finally {
          setCheckingAvailability(false);
        }
      }
      
      setShowCreateDialog(true);
    }
  };

  const handleCreateAppointment = async () => {
    setSaving(true);
    try {
      const api = axiosAuth();
      await api.post('/appointments', form);
      await fetchData();
      setShowCreateDialog(false);
      setForm({});
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to create appointment');
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateAppointment = async (status) => {
    setSaving(true);
    try {
      const api = axiosAuth();
      if (status === 'cancelled') {
        await api.delete(`/appointments/${selectedAppointment.id}`);
      } else {
        await api.post(`/appointments/${selectedAppointment.id}/verify`);
      }
      await fetchData();
      setShowDetailsDialog(false);
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to update appointment');
    } finally {
      setSaving(false);
    }
  };

  const navigateDate = (direction) => {
    const newDate = new Date(currentDate);
    if (view === 'month') {
      newDate.setMonth(currentDate.getMonth() + direction);
    } else if (view === 'week') {
      newDate.setDate(currentDate.getDate() + (direction * 7));
    } else {
      newDate.setDate(currentDate.getDate() + direction);
    }
    setCurrentDate(newDate);
  };

  const goToToday = () => setCurrentDate(new Date());

  const formatDate = (date) => {
    return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
  };

  const formatWeekRange = () => {
    const week = getWeekDays(currentDate);
    const start = week[0].toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const end = week[6].toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    return `${start} - ${end}`;
  };

  const getStatusColor = (status) => {
    const colors = {
      'pending_verification': 'bg-amber-100 text-amber-700 border-amber-200',
      'scheduled': 'bg-teal-100 text-teal-700 border-teal-200',
      'completed': 'bg-gray-100 text-gray-700 border-gray-200',
      'cancelled': 'bg-red-100 text-red-700 border-red-200',
      'no_show': 'bg-orange-100 text-orange-700 border-orange-200'
    };
    return colors[status] || 'bg-blue-100 text-blue-700 border-blue-200';
  };

  const getTypeColor = (type) => {
    const colors = {
      'Cleaning': 'bg-blue-500',
      'Checkup': 'bg-teal-500',
      'Consultation': 'bg-violet-500',
      'Emergency': 'bg-red-500',
      'Follow-up': 'bg-amber-500'
    };
    return colors[type] || 'bg-gray-500';
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Calendar</h1>
          <p className="text-sm text-gray-500 mt-1">Appointment scheduling and availability</p>
        </div>
        <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => {
          setSelectedSlot({ date: new Date(), time: '09:00' });
          setForm({
            patient_id: '',
            patient_name: '',
            patient_phone: '',
            appointment_date: new Date().toISOString().split('T')[0],
            appointment_time: '09:00',
            service_type: 'Cleaning',
            provider_id: '',
            location_id: '',
            notes: ''
          });
          setShowCreateDialog(true);
        }}>
          <Plus className="w-4 h-4 mr-1" /> New Appointment
        </Button>
      </div>

      {/* Filters */}
      <Card className="border-gray-200/80">
        <CardContent className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs">Search Patient</Label>
              <div className="relative">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Patient name..."
                  value={filters.search}
                  onChange={e => setFilters({ ...filters, search: e.target.value })}
                  className="pl-8 h-9"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Provider</Label>
              <select
                value={filters.provider}
                onChange={e => setFilters({ ...filters, provider: e.target.value })}
                className="w-full h-9 rounded-md border border-gray-200 bg-white px-3 text-sm"
              >
                <option value="all">All Providers</option>
                {providers.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Location</Label>
              <select
                value={filters.location}
                onChange={e => setFilters({ ...filters, location: e.target.value })}
                className="w-full h-9 rounded-md border border-gray-200 bg-white px-3 text-sm"
              >
                <option value="all">All Locations</option>
                {locations.map(l => (
                  <option key={l.id} value={l.id}>{l.name}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Status</Label>
              <select
                value={filters.status}
                onChange={e => setFilters({ ...filters, status: e.target.value })}
                className="w-full h-9 rounded-md border border-gray-200 bg-white px-3 text-sm"
              >
                <option value="all">All Status</option>
                <option value="pending_verification">Pending</option>
                <option value="scheduled">Scheduled</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
            <div className="flex items-end">
              <Button
                variant="outline"
                size="sm"
                className="h-9 w-full"
                onClick={() => setFilters({ provider: 'all', location: 'all', status: 'all', search: '' })}
              >
                <X className="w-3.5 h-3.5 mr-1" /> Clear
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Calendar Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => navigateDate(-1)}>
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={() => navigateDate(1)}>
            <ChevronRight className="w-4 h-4" />
          </Button>
          <Button variant="outline" size="sm" onClick={goToToday}>
            Today
          </Button>
          <div className="text-sm font-semibold text-gray-900 ml-2">
            {view === 'month' ? formatDate(currentDate) : view === 'week' ? formatWeekRange() : currentDate.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
          </div>
        </div>

        <Tabs value={view} onValueChange={setView} className="w-auto">
          <TabsList className="grid w-[280px] grid-cols-3">
            <TabsTrigger value="month">Month</TabsTrigger>
            <TabsTrigger value="week">Week</TabsTrigger>
            <TabsTrigger value="day">Day</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Calendar Views */}
      <Card className="border-gray-200/80">
        <CardContent className="p-0">
          {view === 'month' && <MonthView currentDate={currentDate} getMonthDays={getMonthDays} getAppointmentsForDate={getAppointmentsForDate} handleSlotClick={handleSlotClick} getStatusColor={getStatusColor} getTypeColor={getTypeColor} />}
          {view === 'week' && <WeekView currentDate={currentDate} getWeekDays={getWeekDays} getTimeSlots={getTimeSlots} getAppointmentAtTime={getAppointmentAtTime} handleSlotClick={handleSlotClick} getStatusColor={getStatusColor} getTypeColor={getTypeColor} />}
          {view === 'day' && <DayView currentDate={currentDate} getTimeSlots={getTimeSlots} getAppointmentAtTime={getAppointmentAtTime} handleSlotClick={handleSlotClick} getStatusColor={getStatusColor} getTypeColor={getTypeColor} />}
        </CardContent>
      </Card>

      {/* Create Appointment Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>New Appointment</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2 space-y-1.5">
                <Label>Patient *</Label>
                <select
                  value={form.patient_id || ''}
                  onChange={e => {
                    const patient = patients.find(p => p.id === e.target.value);
                    setForm({
                      ...form,
                      patient_id: e.target.value,
                      patient_name: patient?.name || patient?.full_name || '',
                      patient_phone: patient?.phone || ''
                    });
                  }}
                  className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm"
                >
                  <option value="">Select patient...</option>
                  {patients.map(p => (
                    <option key={p.id} value={p.id}>{p.name || p.full_name} - {p.phone}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label>Date *</Label>
                <Input
                  type="date"
                  value={form.appointment_date || ''}
                  onChange={e => setForm({ ...form, appointment_date: e.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Time *</Label>
                <Input
                  type="time"
                  value={form.appointment_time || ''}
                  onChange={e => setForm({ ...form, appointment_time: e.target.value })}
                />
              </div>
              <div className="col-span-2 space-y-1.5">
                <Label>Location *</Label>
                <select
                  value={form.location_id || ''}
                  onChange={async e => {
                    setForm({ ...form, location_id: e.target.value, provider_id: '' });
                    
                    // Fetch available providers when location changes
                    if (e.target.value && form.appointment_date) {
                      setCheckingAvailability(true);
                      try {
                        const api = axiosAuth();
                        const response = await api.post('/appointments/route', {
                          appointment_type: form.service_type || 'Cleaning',
                          location_id: e.target.value,
                          date: form.appointment_date,
                          is_emergency: false
                        });
                        setAvailableProviders(response.data.providers || []);
                      } catch (err) {
                        console.error('Failed to fetch providers:', err);
                        setAvailableProviders([]);
                      } finally {
                        setCheckingAvailability(false);
                      }
                    }
                  }}
                  className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm"
                >
                  <option value="">Select location...</option>
                  {locations.map(l => (
                    <option key={l.id} value={l.id}>{l.name}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label>Service Type</Label>
                <select
                  value={form.service_type || 'Cleaning'}
                  onChange={e => setForm({ ...form, service_type: e.target.value })}
                  className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm"
                >
                  <option value="Cleaning">Cleaning</option>
                  <option value="Checkup">Checkup</option>
                  <option value="Consultation">Consultation</option>
                  <option value="Emergency">Emergency</option>
                  <option value="Follow-up">Follow-up</option>
                  <option value="Root Canal">Root Canal</option>
                  <option value="Extraction">Extraction</option>
                  <option value="Filling">Filling</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <Label>Provider *</Label>
                <select
                  value={form.provider_id || ''}
                  onChange={e => setForm({ ...form, provider_id: e.target.value })}
                  className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm"
                  disabled={checkingAvailability || !form.location_id}
                >
                  <option value="">
                    {checkingAvailability ? 'Loading providers...' : 'Select provider...'}
                  </option>
                  {availableProviders.map(p => (
                    <option key={p.provider_id} value={p.provider_id}>
                      {p.provider_name} {p.is_on_call ? '⚡' : ''} ({p.available_times.length} slots)
                    </option>
                  ))}
                  {!checkingAvailability && availableProviders.length === 0 && form.location_id && (
                    <option value="" disabled>No providers available</option>
                  )}
                </select>
                {form.provider_id && availableProviders.find(p => p.provider_id === form.provider_id) && (
                  <p className="text-xs text-teal-600">
                    ✓ Available at {form.appointment_time}
                  </p>
                )}
              </div>
              <div className="col-span-2 space-y-1.5">
                <Label>Notes</Label>
                <Input
                  value={form.notes || ''}
                  onChange={e => setForm({ ...form, notes: e.target.value })}
                  placeholder="Additional notes..."
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>Cancel</Button>
            <Button onClick={handleCreateAppointment} disabled={saving || !form.patient_id || !form.provider_id || !form.location_id}>
              {saving ? 'Creating...' : 'Create Appointment'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Appointment Details Dialog */}
      <Dialog open={showDetailsDialog} onOpenChange={setShowDetailsDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Appointment Details</DialogTitle>
          </DialogHeader>
          {selectedAppointment && (
            <div className="space-y-4 py-4">
              <div className="flex items-start justify-between">
                <div className="space-y-3 flex-1">
                  <div>
                    <p className="text-sm text-gray-500">Patient</p>
                    <p className="text-base font-semibold">{selectedAppointment.patient_name}</p>
                  </div>
                  {selectedAppointment.provider_name && (
                    <div>
                      <p className="text-sm text-gray-500">Provider</p>
                      <div className="flex items-center gap-2">
                        <p className="text-base font-medium">{selectedAppointment.provider_name}</p>
                        {providers.find(p => p.id === selectedAppointment.provider_id)?.on_call && (
                          <Badge className="text-[10px] bg-amber-100 text-amber-700">On-Call</Badge>
                        )}
                      </div>
                      {selectedAppointment.provider_location && (
                        <p className="text-xs text-gray-500 mt-0.5">at {selectedAppointment.provider_location}</p>
                      )}
                    </div>
                  )}
                  <div>
                    <p className="text-sm text-gray-500">Date & Time</p>
                    <p className="text-base">{new Date(selectedAppointment.appointment_date).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })} at {selectedAppointment.appointment_time}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500">Service</p>
                    <p className="text-base">{selectedAppointment.service_type || selectedAppointment.reason || 'Not specified'}</p>
                  </div>
                  {selectedAppointment.notes && (
                    <div>
                      <p className="text-sm text-gray-500">Notes</p>
                      <p className="text-sm">{selectedAppointment.notes}</p>
                    </div>
                  )}
                </div>
                <Badge className={getStatusColor(selectedAppointment.status)}>
                  {selectedAppointment.status?.replace('_', ' ')}
                </Badge>
              </div>
            </div>
          )}
          <DialogFooter className="flex gap-2">
            <Button variant="outline" onClick={() => setShowDetailsDialog(false)}>Close</Button>
            {selectedAppointment?.status === 'pending_verification' && (
              <Button onClick={() => handleUpdateAppointment('scheduled')} disabled={saving}>
                Verify
              </Button>
            )}
            {selectedAppointment?.status !== 'cancelled' && (
              <Button variant="outline" className="text-red-600" onClick={() => handleUpdateAppointment('cancelled')} disabled={saving}>
                Cancel Appointment
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// Month View Component
function MonthView({ currentDate, getMonthDays, getAppointmentsForDate, handleSlotClick, getStatusColor, getTypeColor }) {
  const days = getMonthDays(currentDate);
  const today = new Date().toISOString().split('T')[0];
  const currentMonth = currentDate.getMonth();

  return (
    <div className="p-4">
      <div className="grid grid-cols-7 gap-px bg-gray-200 rounded-lg overflow-hidden">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
          <div key={day} className="bg-gray-50 px-3 py-2 text-center">
            <p className="text-xs font-semibold text-gray-600">{day}</p>
          </div>
        ))}
        {days.map((day, idx) => {
          const dateStr = day.toISOString().split('T')[0];
          const isToday = dateStr === today;
          const isCurrentMonth = day.getMonth() === currentMonth;
          const dayAppointments = getAppointmentsForDate(day);

          return (
            <div
              key={idx}
              className={`bg-white min-h-[100px] p-2 ${!isCurrentMonth ? 'opacity-40' : ''} ${isToday ? 'ring-2 ring-teal-500' : ''} cursor-pointer hover:bg-gray-50 transition-colors`}
              onClick={() => handleSlotClick(day, '09:00')}
            >
              <div className="flex items-center justify-between mb-1">
                <span className={`text-sm font-semibold ${isToday ? 'text-teal-600' : 'text-gray-900'}`}>
                  {day.getDate()}
                </span>
                {dayAppointments.length > 0 && (
                  <span className="text-xs text-gray-500">{dayAppointments.length}</span>
                )}
              </div>
              <div className="space-y-1">
                {dayAppointments.slice(0, 3).map(apt => (
                  <div
                    key={apt.id}
                    className={`text-xs p-1 rounded border ${getStatusColor(apt.status)}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSlotClick(day, apt.appointment_time);
                    }}
                  >
                    <div className="flex items-center gap-1">
                      <div className={`w-1.5 h-1.5 rounded-full ${getTypeColor(apt.service_type || apt.reason)}`} />
                      <span className="truncate font-medium">{apt.appointment_time}</span>
                    </div>
                    <p className="truncate text-[10px] mt-0.5">{apt.patient_name}</p>
                  </div>
                ))}
                {dayAppointments.length > 3 && (
                  <p className="text-[10px] text-gray-500 text-center">+{dayAppointments.length - 3} more</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Week View Component
function WeekView({ currentDate, getWeekDays, getTimeSlots, getAppointmentAtTime, handleSlotClick, getStatusColor, getTypeColor }) {
  const week = getWeekDays(currentDate);
  const slots = getTimeSlots();
  const today = new Date().toISOString().split('T')[0];

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[800px]">
        <div className="grid grid-cols-8 border-b border-gray-200">
          <div className="p-2 text-xs font-semibold text-gray-600">Time</div>
          {week.map(day => {
            const isToday = day.toISOString().split('T')[0] === today;
            return (
              <div key={day} className={`p-2 text-center border-l border-gray-200 ${isToday ? 'bg-teal-50' : ''}`}>
                <p className="text-xs font-semibold text-gray-600">{day.toLocaleDateString('en-US', { weekday: 'short' })}</p>
                <p className={`text-lg font-bold ${isToday ? 'text-teal-600' : 'text-gray-900'}`}>{day.getDate()}</p>
              </div>
            );
          })}
        </div>
        <div className="divide-y divide-gray-100">
          {slots.map(time => (
            <div key={time} className="grid grid-cols-8">
              <div className="p-2 text-xs text-gray-500 font-medium">{time}</div>
              {week.map(day => {
                const apt = getAppointmentAtTime(day, time);
                return (
                  <div
                    key={`${day}-${time}`}
                    className="border-l border-gray-100 p-1 cursor-pointer hover:bg-gray-50 transition-colors min-h-[40px]"
                    onClick={() => handleSlotClick(day, time)}
                  >
                    {apt ? (
                      <div className={`text-xs p-1.5 rounded border ${getStatusColor(apt.status)} h-full`}>
                        <div className="flex items-center gap-1 mb-0.5">
                          <div className={`w-1.5 h-1.5 rounded-full ${getTypeColor(apt.service_type || apt.reason)}`} />
                          <span className="font-semibold truncate">{apt.patient_name}</span>
                        </div>
                        <p className="text-[10px] truncate">{apt.service_type || apt.reason}</p>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Day View Component
function DayView({ currentDate, getTimeSlots, getAppointmentAtTime, handleSlotClick, getStatusColor, getTypeColor }) {
  const slots = getTimeSlots();

  return (
    <div className="p-4">
      <div className="max-w-3xl mx-auto space-y-1">
        {slots.map(time => {
          const apt = getAppointmentAtTime(currentDate, time);
          return (
            <div
              key={time}
              className="grid grid-cols-12 gap-3 border-b border-gray-100 py-2 cursor-pointer hover:bg-gray-50 transition-colors"
              onClick={() => handleSlotClick(currentDate, time)}
            >
              <div className="col-span-2 text-sm font-semibold text-gray-600">{time}</div>
              <div className="col-span-10">
                {apt ? (
                  <div className={`p-3 rounded-lg border ${getStatusColor(apt.status)}`}>
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <div className={`w-2 h-2 rounded-full ${getTypeColor(apt.service_type || apt.reason)}`} />
                          <span className="font-semibold text-sm">{apt.patient_name}</span>
                        </div>
                        <p className="text-xs text-gray-600">{apt.service_type || apt.reason}</p>
                        {apt.notes && <p className="text-xs text-gray-500 mt-1">{apt.notes}</p>}
                      </div>
                      <Badge className={getStatusColor(apt.status)} variant="outline">
                        {apt.status?.replace('_', ' ')}
                      </Badge>
                    </div>
                  </div>
                ) : (
                  <div className="p-3 text-sm text-gray-400 border border-dashed border-gray-200 rounded-lg text-center">
                    Available - Click to book
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
