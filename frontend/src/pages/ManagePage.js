import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../config/api';

import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';

import {
  MapPin, Briefcase, UserCog, Plus, Edit2, Trash2, Loader2,
  Shield, Clock
} from 'lucide-react';

export default function ManagePage() {
  const { isAdmin } = useAuth();

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

  useEffect(() => {
    fetchAll();
  }, []);

  const fetchAll = async () => {
    try {
      const [locRes, provRes, userRes] = await Promise.all([
        api.get('/locations'),
        api.get('/providers'),
        api.get('/practice/users')
      ]);

      setLocations(locRes.data);
      setProviders(provRes.data);
      setUsers(userRes.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const saveLocation = async () => {
    setSaving(true);
    try {
      if (form.id) {
        await api.put(`/locations/${form.id}`, form);
      } else {
        await api.post('/locations', form);
      }
      await fetchAll();
      setDialog(null);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const saveProvider = async () => {
    setSaving(true);
    try {
      if (form.id) {
        await api.put(`/providers/${form.id}`, form);
      } else {
        await api.post('/providers', form);
      }
      await fetchAll();
      setDialog(null);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const inviteUser = async () => {
    setSaving(true);
    try {
      const res = await api.post('/auth/invite', form);
      alert(`User invited! Temporary password: ${res.data.temporary_password}`);
      await fetchAll();
      setDialog(null);
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed');
    } finally {
      setSaving(false);
    }
  };

  const openLocationDialog = (location = null) => {
    if (location) {
      setForm({ ...location });
      setEditingItem(location);
    } else {
      setForm({
        name: '',
        address: '',
        city: '',
        province: '',
        postal_code: '',
        phone: '',
        timezone: 'America/Toronto',
        is_active: true
      });
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
        specialties: provider.specialties || [],
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

  const deleteLocation = async (id) => {
    if (!window.confirm('Delete this location? This cannot be undone.')) return;
    try {
      await api.delete(`/locations/${id}`);
      await fetchAll();
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to delete location');
    }
  };

  const deleteProvider = async (id) => {
    if (!window.confirm('Delete this provider? This cannot be undone.')) return;
    try {
      await api.delete(`/providers/${id}`);
      await fetchAll();
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to delete provider');
    }
  };

  const roleColors = {
    admin: 'bg-violet-100 text-violet-700',
    staff: 'bg-teal-100 text-teal-700',
    provider: 'bg-blue-100 text-blue-700',
    auditor: 'bg-amber-100 text-amber-700',
  };

  if (!isAdmin) {
    return (
      <div className="flex items-center justify-center h-96">
        <Card className="border-amber-200/80 bg-amber-50/50 max-w-md">
          <CardContent className="p-6 text-center">
            <Shield className="w-12 h-12 text-amber-600 mx-auto mb-3" />
            <h3 className="text-lg font-semibold text-gray-900 mb-1">Admin Access Required</h3>
            <p className="text-sm text-gray-600">
              Only practice administrators can manage locations, providers, and team members.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Manage Practice</h1>
        <p className="text-sm text-gray-500 mt-1">Locations, providers, and team members</p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-3 mb-6">
          <TabsTrigger value="locations" className="gap-1.5">
            <MapPin className="w-4 h-4" />Locations
          </TabsTrigger>
          <TabsTrigger value="providers" className="gap-1.5">
            <Briefcase className="w-4 h-4" />Providers
          </TabsTrigger>
          <TabsTrigger value="users" className="gap-1.5">
            <UserCog className="w-4 h-4" />Team
          </TabsTrigger>
        </TabsList>

        {/* LOCATIONS TAB */}
        <TabsContent value="locations" className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              {locations.length} location{locations.length !== 1 ? 's' : ''}
            </p>
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
                            {!loc.is_active && (
                              <Badge variant="outline" className="text-[10px] text-red-500">
                                Inactive
                              </Badge>
                            )}
                          </div>

                          <p className="text-xs text-gray-500 mb-1">
                            {[loc.address, loc.city, loc.province, loc.postal_code]
                              .filter(Boolean)
                              .join(', ') || 'No address set'}
                          </p>

                          <div className="flex items-center gap-3 text-xs text-gray-400">
                            {loc.phone && <span>{loc.phone}</span>}
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {loc.timezone}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="flex gap-1 ml-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => openLocationDialog(loc)}
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </Button>

                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-500 hover:text-red-600"
                          onClick={() => deleteLocation(loc.id)}
                        >
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
            <p className="text-sm text-gray-600">
              {providers.length} active provider{providers.length !== 1 ? 's' : ''}
            </p>
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
                const providerLocations = locations.filter(l =>
                  (prov.location_ids || []).includes(l.id)
                );
                const legacyLocation = locations.find(l => l.id === prov.location_id);
                const displayLocations =
                  providerLocations.length > 0
                    ? providerLocations
                    : legacyLocation
                    ? [legacyLocation]
                    : [];

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
                              <Badge variant="outline" className="text-[10px]">
                                {prov.role || 'dentist'}
                              </Badge>
                              {prov.on_call && (
                                <Badge className="text-[10px] bg-amber-100 text-amber-700">
                                  On-Call
                                </Badge>
                              )}
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
                                  Services:{' '}
                                  {(prov.appointment_types || []).slice(0, 3).join(', ')}
                                  {(prov.appointment_types || []).length > 3 &&
                                    ` +${prov.appointment_types.length - 3} more`}
                                </p>
                              )}

                              {prov.license_number && <p>License: {prov.license_number}</p>}

                              {prov.specialties && prov.specialties.length > 0 && (
                                <p className="flex items-center gap-1 flex-wrap mt-1">
                                  {prov.specialties.map(s => (
                                    <Badge key={s} variant="outline" className="text-[10px]">
                                      {s}
                                    </Badge>
                                  ))}
                                </p>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="flex gap-1 ml-2">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={() => openProviderDialog(prov)}
                          >
                            <Edit2 className="w-3.5 h-3.5" />
                          </Button>

                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-red-500 hover:text-red-600"
                            onClick={() => deleteProvider(prov.id)}
                          >
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
            <p className="text-sm text-gray-600">
              {users.length} team member{users.length !== 1 ? 's' : ''}
            </p>

            <Button
              className="bg-teal-600 hover:bg-teal-700"
              onClick={() => {
                setForm({ email: '', full_name: '', role: 'staff' });
                setError('');
                setDialog('user');
              }}
            >
              <Plus className="w-4 h-4 mr-1" /> Invite Member
            </Button>
          </div>

          <div className="grid gap-3">
            {users.map(u => (
              <Card key={u.id} className="border-gray-200/80">
                <CardContent className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-teal-100 flex items-center justify-center">
                      <span className="text-sm font-bold text-teal-700">
                        {u.full_name?.charAt(0) || '?'}
                      </span>
                    </div>

                    <div>
                      <p className="text-sm font-semibold text-gray-900">{u.full_name}</p>
                      <p className="text-xs text-gray-500">{
