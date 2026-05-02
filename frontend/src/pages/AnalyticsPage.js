import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import {
  Phone, PhoneIncoming, PhoneMissed, Calendar, UserPlus,
  ShieldCheck, AlertTriangle, TrendingUp, BarChart3
} from 'lucide-react';
import { mockAnalytics } from '../data/mockData';

export default function AnalyticsPage({ useMock = false }) {
  const { axiosAuth } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnalytics = async () => {
      if (useMock) { setAnalytics(mockAnalytics); setLoading(false); return; }
      try {
        const api = axiosAuth();
        const res = await api.get('/analytics/dashboard');
        setAnalytics(res.data);
      } catch { setAnalytics(mockAnalytics); } finally { setLoading(false); }
    };
    fetchAnalytics();
  }, [axiosAuth, useMock]);

  if (loading || !analytics) {
    return <div className="flex justify-center py-12"><div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" /></div>;
  }

  const { metrics } = analytics;

  const callCards = [
    { label: 'Total Calls', value: metrics.call_volume.total_calls, icon: Phone, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: 'Answered', value: metrics.call_volume.calls_answered, icon: PhoneIncoming, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'Missed', value: metrics.call_volume.calls_missed, icon: PhoneMissed, color: 'text-red-600', bg: 'bg-red-50' },
    { label: 'Emergency', value: metrics.call_volume.emergency_calls, icon: AlertTriangle, color: 'text-amber-600', bg: 'bg-amber-50' },
  ];

  const answerRate = metrics.call_volume.total_calls > 0
    ? ((metrics.call_volume.calls_answered / metrics.call_volume.total_calls) * 100).toFixed(1)
    : 0;

  const confirmRate = metrics.appointments.total_requested > 0
    ? ((metrics.appointments.confirmed / metrics.appointments.total_requested) * 100).toFixed(1)
    : 0;

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
        <p className="text-sm text-gray-500 mt-1">Last 30 days performance overview</p>
      </div>

      {/* Call Volume */}
      <div>
        <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
          <Phone className="w-4 h-4" /> Call Volume
        </h2>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {callCards.map((card, i) => {
            const Icon = card.icon;
            return (
              <Card key={i} className="border-gray-200/80">
                <CardContent className="p-4">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl ${card.bg} flex items-center justify-center`}>
                      <Icon className={`w-5 h-5 ${card.color}`} />
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-gray-900">{card.value}</p>
                      <p className="text-xs text-gray-500">{card.label}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Key Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Answer Rate */}
        <Card className="border-gray-200/80">
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-500">Answer Rate</h3>
              <TrendingUp className="w-4 h-4 text-emerald-500" />
            </div>
            <p className="text-3xl font-bold text-gray-900">{answerRate}%</p>
            <div className="mt-3 w-full bg-gray-100 rounded-full h-2">
              <div className="bg-emerald-500 h-2 rounded-full transition-all" style={{ width: `${answerRate}%` }} />
            </div>
          </CardContent>
        </Card>

        {/* Appointment Confirmation */}
        <Card className="border-gray-200/80">
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-500">Confirmation Rate</h3>
              <Calendar className="w-4 h-4 text-blue-500" />
            </div>
            <p className="text-3xl font-bold text-gray-900">{confirmRate}%</p>
            <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
              <span>{metrics.appointments.confirmed} confirmed</span>
              <span>{metrics.appointments.pending} pending</span>
            </div>
          </CardContent>
        </Card>

        {/* Consent Rate */}
        <Card className="border-gray-200/80">
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-medium text-gray-500">Consent Rate</h3>
              <ShieldCheck className="w-4 h-4 text-violet-500" />
            </div>
            <p className="text-3xl font-bold text-gray-900">{metrics.consent.consent_rate}%</p>
            <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
              <span>{metrics.consent.consent_given} of {metrics.consent.total_intakes}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Additional Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="border-gray-200/80">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <UserPlus className="w-4 h-4 text-teal-500" /> Appointments Summary
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Total Requested</span>
                <span className="text-sm font-semibold">{metrics.appointments.total_requested}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Confirmed</span>
                <span className="text-sm font-semibold text-emerald-600">{metrics.appointments.confirmed}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Pending Verification</span>
                <span className="text-sm font-semibold text-amber-600">{metrics.appointments.pending}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Duplicates Prevented</span>
                <span className="text-sm font-semibold text-violet-600">{metrics.duplicates.duplicates_prevented}</span>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-gray-200/80">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-500" /> Safety & Compliance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Emergency Calls Routed</span>
                <span className="text-sm font-semibold text-red-600">{metrics.emergency.emergency_routed}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Consent Captured</span>
                <span className="text-sm font-semibold text-emerald-600">{metrics.consent.consent_given}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Duplicate Patients Caught</span>
                <span className="text-sm font-semibold">{metrics.duplicates.duplicates_prevented}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Overall Compliance</span>
                <span className="text-sm font-semibold text-emerald-600">Active</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
