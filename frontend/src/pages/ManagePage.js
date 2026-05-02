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
  MapPin, Briefcase, UserCog, Plus, Edit2, Trash2, Loader2, Shield, Mail, Clock
} from 'lucide-react';

export default function ManagePage() {
  const { axiosAuth, user, isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState('locations');
  const [locations, setLocations] = useState([]);
  const [providers, setProviders] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(null); // 'location' | 'provider' | 'user'
  const [editingItem, setEditingItem] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    try {
      const api = axiosAuth();
      const [locRes, provRes, userRes] = await Promise.all([
        api.get('/locations'), api.get('/providers'), api.get('/practice/users')
      ]);
      setLocations(locRes.data); setProviders(provRes.data); setUsers(userRes.data);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  };

  const saveLocation = async () => {
    setSaving(true);
    try {
      const api = axiosAuth();
      if (form.id) { await api.put(`/locations/${form.id}`, form); }
      else { await api.post('/locations', form); }
      await fetchAll(); setDialog(null);
    } catch (e) { console.error(e); } finally { setSaving(false); }
  };

  const saveProvider = async () => {
    setSaving(true);
    try {
      const api = axiosAuth();
      if (form.id) { await api.put(`/providers/${form.id}`, form); }
      else { await api.post('/providers', form); }
      await fetchAll(); setDialog(null);
    } catch (e) { console.error(e); } finally { setSaving(false); }
  };

  const inviteUser = async () => {
    setSaving(true);
    try {
      const api = axiosAuth();
      const res = await api.post('/auth/invite', form);
      alert(`User invited! Temporary password: ${res.data.temporary_password}`);
      await fetchAll(); setDialog(null);
    } catch (e) { alert(e.response?.data?.detail || 'Failed'); } finally { setSaving(false); }
  };

  // Dialog opener functions
  const openLocationDialog = (location = null) => {
    if (location) {
      setForm({ ...location });
      setEditingItem(location);
    } else {
      setForm({ name: '', address: '', city: '', province: '', postal_code: '', phone: '', timezone: 'America/Toronto', is_active: true });
      setEditingItem(null);
    }
    setError('');
    setDialog('location');
  };

  const openProviderDialog = (provider = null) => {
    if (provider) {
      setForm({
        ...provider,
        location_ids: provider.location_ids || (provider.location_id ? [provider.location_id] : []),
        appointment_types: provider.appointment_types || ['Cleaning', 'Checkup', 'Consultation'],
        working_hours: provider.working_hours || {
          monday: [{ start: '09:00', end: '17:00' }],
          tuesday: [{ start: '09:00', end: '17:00' }],
          wednesday: [{ start: '09:00', end: '17:00' }],
          thursday: [{ start: '09:00', end: '17:00' }],
          friday: [{ start: '09:00', end: '17:00' }],
          saturday: [],
          sunday: []
        },
        on_call: provider.on_call || false,
        role: provider.role || 'dentist'
      });
      setEditingItem(provider);
    } else {
      setForm({
        title: 'Dr.',
        name: '',
        role: 'dentist',
        license_number: '',
        location_ids: [],
        appointment_types: ['Cleaning', 'Checkup', 'Consultation'],
        working_hours: {
          monday: [{ start: '09:00', end: '17:00' }],
          tuesday: [{ start: '09:00', end: '17:00' }],
          wednesday: [{ start: '09:00', end: '17:00' }],
          thursday: [{ start: '09:00', end: '17:00' }],
          friday: [{ start: '09:00', end: '17:00' }],
          saturday: [],
          sunday: []
        },
        on_call: false,
        specialties: [],
        is_active: true
      });
      setEditingItem(null);
    }
    setError('');
    setDialog('provider');
  };

  // Delete functions
  const deleteLocation = async (id) => {
    if (!window.confirm('Delete this location? This cannot be undone.')) return;
    try {
      const api = axiosAuth();
      await api.delete(`/locations/${id}`);
      await fetchAll();
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to delete location');
    }
  };

  const deleteProvider = async (id) => {
    if (!window.confirm('Delete this provider? This cannot be undone.')) return;
    try {
      const api = axiosAuth();
      await api.delete(`/providers/${id}`);
      await fetchAll();
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to delete provider');
    }
  };

  const roleColors = {
    admin: 'bg-violet-100 text-violet-700', staff: 'bg-teal-100 text-teal-700',
    provider: 'bg-blue-100 text-blue-700', auditor: 'bg-amber-100 text-amber-700',
  };

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-96">
        <Card className="border-amber-200/80 bg-amber-50/50 max-w-md">
          <CardContent className="p-6 text-center">
            <Shield className="w-12 h-12 text-amber-600 mx-auto mb-3" />
            <h3 className="text-lg font-semibold text-gray-900 mb-1">Admin Access Required</h3>
            <p className="text-sm text-gray-600">Only practice administrators can manage locations, providers, and team members.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loading) {
    return <div className="flex justify-center py-12"><div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" /></div>;
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Manage Practice</h1>
        <p className="text-sm text-gray-500 mt-1">Locations, providers, and team members</p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-3 mb-6">
          <TabsTrigger value="locations" className="gap-1.5"><MapPin className="w-4 h-4" />Locations</TabsTrigger>
          <TabsTrigger value="providers" className="gap-1.5"><Briefcase className="w-4 h-4" />Providers</TabsTrigger>
          <TabsTrigger value="users" className="gap-1.5"><UserCog className="w-4 h-4" />Team</TabsTrigger>
        </TabsList>

        {/* LOCATIONS TAB */}
        <TabsContent value="locations" className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">{locations.length} location{locations.length !== 1 ? 's' : ''}</p>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => openLocationDialog()}>
              <Plus className="w-4 h-4 mr-1" /> Add Location
            </Button>
          </div>
          <div className="grid gap-3">
            {locations.length === 0 ? (
              <Card className="border-gray-200/80">
                <CardContent className="p-8 text-center text-gray-500 text-sm">
                  No locations yet. Add your first practice location.
                </CardContent>
              </Card>
            ) : (
              locations.map(loc => (
                <Card key={loc.id} className="border-gray-200/80 hover:shadow-sm transition-shadow">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3 flex-1">
                        <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
                          <MapPin className="w-5 h-5 text-blue-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <p className="text-sm font-semibold text-gray-900">{loc.name}</p>
                            {!loc.is_active && <Badge variant="outline" className="text-[10px] text-red-500">Inactive</Badge>}
                          </div>
                          <p className="text-xs text-gray-500 mb-1">
                            {[loc.address, loc.city, loc.province, loc.postal_code].filter(Boolean).join(', ') || 'No address set'}
                          </p>
                          <div className="flex items-center gap-3 text-xs text-gray-400">
                            {loc.phone && <span>{loc.phone}</span>}
                            <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{loc.timezone}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex gap-1 ml-2">
                        <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openLocationDialog(loc)}>
                          <Edit2 className="w-3.5 h-3.5" />
                        </Button>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-red-500 hover:text-red-600" onClick={() => deleteLocation(loc.id)}>
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </TabsContent>

        {/* PROVIDERS TAB */}
        <TabsContent value="providers" className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">{providers.length} active provider{providers.length !== 1 ? 's' : ''}</p>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => openProviderDialog()}>
              <Plus className="w-4 h-4 mr-1" /> Add Provider
            </Button>
          </div>
          <div className="grid gap-3">
            {providers.length === 0 ? (
              <Card className="border-gray-200/80">
                <CardContent className="p-8 text-center text-gray-500 text-sm">
                  No providers yet. Add doctors, hygienists, and other care providers.
                </CardContent>
              </Card>
            ) : (
              providers.map(prov => {
                const providerLocations = locations.filter(l => (prov.location_ids || []).includes(l.id));
                const legacyLocation = locations.find(l => l.id === prov.location_id);
                const displayLocations = providerLocations.length > 0 ? providerLocations : (legacyLocation ? [legacyLocation] : []);
                
                return (
                  <Card key={prov.id} className="border-gray-200/80 hover:shadow-sm transition-shadow">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex items-start gap-3 flex-1">
                          <div className="w-10 h-10 rounded-lg bg-violet-50 flex items-center justify-center shrink-0">
                            <Briefcase className="w-5 h-5 text-violet-600" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <p className="text-sm font-semibold text-gray-900">{prov.name}</p>
                              <Badge variant="outline" className="text-[10px]">{prov.role || 'dentist'}</Badge>
                              {prov.on_call && <Badge className="text-[10px] bg-amber-100 text-amber-700">On-Call</Badge>}
                            </div>
                            <div className="space-y-0.5 text-xs text-gray-500">
                              {displayLocations.length > 0 && (
                                <p className="flex items-center gap-1">
                                  <MapPin className="w-3 h-3" />
                                  {displayLocations.map(l => l.name).join(', ')}
                                </p>
                              )}
                              {(prov.appointment_types || []).length > 0 && (
                                <p className="flex items-center gap-1 flex-wrap">
                                  Services: {(prov.appointment_types || []).slice(0, 3).join(', ')}
                                  {(prov.appointment_types || []).length > 3 && ` +${prov.appointment_types.length - 3} more`}
                                </p>
                              )}
                              {prov.license_number && <p>License: {prov.license_number}</p>}
                              {prov.specialties && prov.specialties.length > 0 && (
                                <p className="flex items-center gap-1 flex-wrap mt-1">
                                  {prov.specialties.map(s => <Badge key={s} variant="outline" className="text-[10px]">{s}</Badge>)}
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="flex gap-1 ml-2">
                          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openProviderDialog(prov)}>
                            <Edit2 className="w-3.5 h-3.5" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-red-500 hover:text-red-600" onClick={() => deleteProvider(prov.id)}>
                            <Trash2 className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })
            )}
          </div>
        </TabsContent>

        {/* USERS TAB */}
        <TabsContent value="users" className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">{users.length} team member{users.length !== 1 ? 's' : ''}</p>
            <Button className="bg-teal-600 hover:bg-teal-700" onClick={() => { setForm({ email: '', full_name: '', role: 'staff' }); setError(''); setDialog('user'); }}>
              <Plus className="w-4 h-4 mr-1" /> Invite Member
            </Button>
          </div>
          <div className="grid gap-3">
            {users.map(u => (
              <Card key={u.id} className="border-gray-200/80">
                <CardContent className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-teal-100 flex items-center justify-center">
                      <span className="text-sm font-bold text-teal-700">{u.full_name?.charAt(0) || '?'}</span>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">{u.full_name}</p>
                      <p className="text-xs text-gray-500">{u.email}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className={`text-[10px] ${roleColors[u.role] || 'bg-gray-100 text-gray-600'}`}>{u.role}</Badge>
                    {!u.is_active && <Badge variant="outline" className="text-[10px] text-red-500">Inactive</Badge>}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>

      {/* Location Dialog */}
      <Dialog open={dialog === 'location'} onOpenChange={() => { setDialog(null); setEditingItem(null); setError(''); }}>
        <DialogContent className="max-w-md max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{editingItem ? 'Edit' : 'Add'} Location</DialogTitle></DialogHeader>
          <div className="space-y-3">
            {error && (
              <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-600">{error}</div>
            )}
            <div className="space-y-1.5"><Label>Name *</Label><Input value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Main Office" /></div>
            <div className="space-y-1.5"><Label>Address</Label><Input value={form.address || ''} onChange={e => setForm({ ...form, address: e.target.value })} placeholder="123 Dental St" /></div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5"><Label>City</Label><Input value={form.city || ''} onChange={e => setForm({ ...form, city: e.target.value })} placeholder="Toronto" /></div>
              <div className="space-y-1.5"><Label>Province</Label><Input value={form.province || ''} onChange={e => setForm({ ...form, province: e.target.value })} placeholder="ON" /></div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5"><Label>Postal Code</Label><Input value={form.postal_code || ''} onChange={e => setForm({ ...form, postal_code: e.target.value })} placeholder="M5H 2N2" /></div>
              <div className="space-y-1.5"><Label>Phone</Label><Input value={form.phone || ''} onChange={e => setForm({ ...form, phone: e.target.value })} placeholder="(416) 555-0100" /></div>
            </div>
            <div className="space-y-1.5">
              <Label>Timezone</Label>
              <select value={form.timezone || 'America/Toronto'} onChange={e => setForm({ ...form, timezone: e.target.value })} className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm">
                <option value="America/Toronto">Eastern Time (Toronto)</option>
                <option value="America/Vancouver">Pacific Time (Vancouver)</option>
                <option value="America/Edmonton">Mountain Time (Edmonton)</option>
                <option value="America/Winnipeg">Central Time (Winnipeg)</option>
              </select>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => { setDialog(null); setEditingItem(null); }}>Cancel</Button>
              <Button className="bg-teal-600 hover:bg-teal-700" onClick={saveLocation} disabled={saving}>
                {saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}Save
              </Button>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>

      {/* Provider Dialog - Enhanced with Scheduling */}
      <Dialog open={dialog === 'provider'} onOpenChange={() => { setDialog(null); setEditingItem(null); setError(''); }}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>{editingItem ? 'Edit' : 'Add'} Provider</DialogTitle></DialogHeader>
          <div className="space-y-4">
            {error && (
              <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-600">{error}</div>
            )}
            
            {/* Basic Info */}
            <div className="space-y-3">
              <h4 className="text-sm font-semibold text-gray-900">Basic Information</h4>
              <div className="grid grid-cols-4 gap-2">
                <div className="space-y-1.5">
                  <Label>Title</Label>
                  <select value={form.title || 'Dr.'} onChange={e => setForm({ ...form, title: e.target.value })} className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm">
                    <option value="Dr.">Dr.</option>
                    <option value="Hygienist">Hygienist</option>
                    <option value="Specialist">Specialist</option>
                  </select>
                </div>
                <div className="col-span-3 space-y-1.5">
                  <Label>Name *</Label>
                  <Input value={form.name || ''} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="John Smith" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Role *</Label>
                  <select value={form.role || 'dentist'} onChange={e => setForm({ ...form, role: e.target.value })} className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm">
                    <option value="dentist">Dentist</option>
                    <option value="hygienist">Hygienist</option>
                    <option value="specialist">Specialist</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label>License Number</Label>
                  <Input value={form.license_number || ''} onChange={e => setForm({ ...form, license_number: e.target.value })} placeholder="ON-12345" />
                </div>
              </div>
            </div>

            {/* Locations */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Locations Where Provider Works *</Label>
                <Badge variant="outline" className="text-[10px]">{(form.location_ids || []).length} selected</Badge>
              </div>
              <div className="grid grid-cols-2 gap-2 max-h-32 overflow-y-auto p-2 border rounded-md">
                {/* Deduplicate locations by ID to prevent duplicate display */}
                {locations.filter(l => l.is_active)
                  .filter((loc, index, self) => index === self.findIndex(l => l.id === loc.id))
                  .map(loc => (
                  <label key={loc.id} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-gray-50 p-1.5 rounded">
                    <input
                      type="checkbox"
                      checked={(form.location_ids || []).includes(loc.id)}
                      onChange={e => {
                        const ids = form.location_ids || [];
                        setForm({
                          ...form,
                          location_ids: e.target.checked
                            ? [...ids, loc.id]
                            : ids.filter(id => id !== loc.id)
                        });
                      }}
                      className="rounded"
                    />
                    <span>{loc.name}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Appointment Types */}
            <div className="space-y-2">
              <Label>Services This Provider Handles *</Label>
              <div className="grid grid-cols-3 gap-2">
                {['Cleaning', 'Checkup', 'Consultation', 'Emergency', 'Follow-up', 'Root Canal', 'Extraction', 'Filling'].map(type => (
                  <label key={type} className="flex items-center gap-2 text-sm cursor-pointer hover:bg-gray-50 p-1.5 rounded">
                    <input
                      type="checkbox"
                      checked={(form.appointment_types || []).includes(type)}
                      onChange={e => {
                        const types = form.appointment_types || [];
                        setForm({
                          ...form,
                          appointment_types: e.target.checked
                            ? [...types, type]
                            : types.filter(t => t !== type)
                        });
                      }}
                      className="rounded"
                    />
                    <span>{type}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Working Hours Schedule */}
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Working Hours Schedule
              </Label>
              <div className="space-y-2 border rounded-lg p-3 bg-gray-50">
                {['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].map(day => {
                  const daySchedule = (form.working_hours || {})[day] || [];
                  const isWorking = daySchedule.length > 0;
                  return (
                    <div key={day} className="flex items-center gap-3">
                      <label className="flex items-center gap-2 w-28 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={isWorking}
                          onChange={e => {
                            setForm({
                              ...form,
                              working_hours: {
                                ...(form.working_hours || {}),
                                [day]: e.target.checked ? [{ start: '09:00', end: '17:00' }] : []
                              }
                            });
                          }}
                          className="rounded"
                        />
                        <span className="text-sm font-medium capitalize">{day}</span>
                      </label>
                      {isWorking && daySchedule[0] && (
                        <div className="flex items-center gap-2 flex-1">
                          <Input
                            type="time"
                            value={daySchedule[0].start || '09:00'}
                            onChange={e => {
                              const updated = [...daySchedule];
                              updated[0] = { ...updated[0], start: e.target.value };
                              setForm({
                                ...form,
                                working_hours: { ...(form.working_hours || {}), [day]: updated }
                              });
                            }}
                            className="h-8 text-sm"
                          />
                          <span className="text-xs text-gray-500">to</span>
                          <Input
                            type="time"
                            value={daySchedule[0].end || '17:00'}
                            onChange={e => {
                              const updated = [...daySchedule];
                              updated[0] = { ...updated[0], end: e.target.value };
                              setForm({
                                ...form,
                                working_hours: { ...(form.working_hours || {}), [day]: updated }
                              });
                            }}
                            className="h-8 text-sm"
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* On-Call Status */}
            <div className="flex items-center justify-between p-3 border rounded-lg bg-amber-50">
              <div className="flex-1">
                <Label className="text-sm font-semibold">On-Call for Emergencies</Label>
                <p className="text-xs text-gray-600 mt-0.5">Emergency appointments will prioritize this provider</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={form.on_call || false}
                  onChange={e => setForm({ ...form, on_call: e.target.checked })}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-teal-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-teal-600"></div>
              </label>
            </div>

            {/* Additional Fields */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>ITRANS Provider Number</Label>
                <Input value={form.itrans_provider_number || ''} onChange={e => setForm({ ...form, itrans_provider_number: e.target.value })} placeholder="Optional" />
              </div>
              <div className="space-y-1.5">
                <Label>Specialties (comma-separated)</Label>
                <Input
                  value={Array.isArray(form.specialties) ? form.specialties.join(', ') : ''}
                  onChange={e => setForm({ ...form, specialties: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                  placeholder="Orthodontics, etc."
                />
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => { setDialog(null); setEditingItem(null); }}>Cancel</Button>
              <Button className="bg-teal-600 hover:bg-teal-700" onClick={saveProvider} disabled={saving || !form.name || (form.location_ids || []).length === 0}>
                {saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
                {saving ? 'Saving...' : 'Save Provider'}
              </Button>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>

      {/* Invite User Dialog */}
      <Dialog open={dialog === 'user'} onOpenChange={() => { setDialog(null); setError(''); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader><DialogTitle>Invite Team Member</DialogTitle></DialogHeader>
          <div className="space-y-3">
            {error && (
              <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-600">{error}</div>
            )}
            <div className="space-y-1.5"><Label>Full Name *</Label><Input value={form.full_name || ''} onChange={e => setForm({ ...form, full_name: e.target.value })} placeholder="Jane Doe" /></div>
            <div className="space-y-1.5"><Label>Email *</Label><Input type="email" value={form.email || ''} onChange={e => setForm({ ...form, email: e.target.value })} placeholder="jane@example.com" /></div>
            <div className="space-y-1.5">
              <Label>Role</Label>
              <select value={form.role || 'staff'} onChange={e => setForm({ ...form, role: e.target.value })} className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm">
                <option value="staff">Staff</option>
                <option value="admin">Admin</option>
                <option value="provider">Provider</option>
                <option value="auditor">Auditor</option>
              </select>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDialog(null)}>Cancel</Button>
              <Button className="bg-teal-600 hover:bg-teal-700" onClick={inviteUser} disabled={saving}>
                {saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}Invite
              </Button>
            </DialogFooter>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
