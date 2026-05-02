import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import {
  Calendar, Users, Phone, Clock, AlertTriangle,
  CheckCircle2, ArrowRight, TrendingUp, PhoneIncoming
} from 'lucide-react';
import { mockStats, mockAppointments, mockCallLogs, mockNotifications } from '../data/mockData';

export default function DashboardPage({ useMock = false }) {
  const { axiosAuth } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(mockStats);
  const [recentAppointments, setRecentAppointments] = useState([]);
  const [recentCalls, setRecentCalls] = useState([]);
  const [activeCalls, setActiveCalls] = useState([]);
  const [pendingNotifications, setPendingNotifications] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      if (useMock) {
        setStats(mockStats);
        setRecentAppointments(mockAppointments.slice(0, 4));
        setRecentCalls(mockCallLogs.slice(0, 3));
        setPendingNotifications(mockNotifications);
        setLoading(false);
        return;
      }
      try {
        const api = axiosAuth();
        const [statsRes, aptsRes, callsRes, notifsRes] = await Promise.all([
          api.get('/stats'),
          api.get('/appointments'),
          api.get('/call-logs'),
          api.get('/notifications')
        ]);
        setStats(statsRes.data);
        setRecentAppointments(aptsRes.data.slice(0, 4));
        
        // Separate active calls from recent calls
        const allCalls = callsRes.data || [];
        const active = allCalls.filter(c => c.call_status === 'started' && !c.end_timestamp);
        const completed = allCalls.filter(c => c.call_status !== 'started' || c.end_timestamp);
        
        setActiveCalls(active);
        setRecentCalls(completed.slice(0, 3));
        setPendingNotifications(notifsRes.data.filter(n => n.status === 'unread'));
      } catch (err) {
        console.error('Failed to fetch dashboard data:', err);
        // Fall back to mock on error
        setStats(mockStats);
        setRecentAppointments(mockAppointments.slice(0, 4));
        setRecentCalls(mockCallLogs.slice(0, 3));
        setActiveCalls([]);
        setPendingNotifications(mockNotifications);
      } finally {
        setLoading(false);
      }
    };
    
    // Initial fetch
    fetchData();
    
    // Poll for updates every 8 seconds to refresh active calls
    const pollInterval = setInterval(() => {
      fetchData();
    }, 8000);
    
    // Cleanup interval on unmount
    return () => clearInterval(pollInterval);
  }, [axiosAuth, useMock]);

  const statCards = [
    { label: "Today's Appointments", value: stats.today_appointments, icon: Calendar, color: 'bg-blue-50 text-blue-600', iconBg: 'bg-blue-100', path: '/appointments' },
    { label: 'Total Patients', value: stats.total_patients, icon: Users, color: 'bg-emerald-50 text-emerald-600', iconBg: 'bg-emerald-100', path: '/patients' },
    { label: 'Total Calls', value: stats.total_calls, icon: Phone, color: 'bg-violet-50 text-violet-600', iconBg: 'bg-violet-100', path: '/call-logs' },
    { label: 'Scheduled', value: stats.scheduled_appointments, icon: CheckCircle2, color: 'bg-amber-50 text-amber-600', iconBg: 'bg-amber-100', path: '/appointments' },
    ...(stats.providers !== undefined ? [{ label: 'Providers', value: stats.providers, icon: Users, color: 'bg-cyan-50 text-cyan-600', iconBg: 'bg-cyan-100', path: '/manage' }] : []),
    ...(stats.pending_claims !== undefined && stats.pending_claims > 0 ? [{ label: 'Pending Claims', value: stats.pending_claims, icon: CheckCircle2, color: 'bg-red-50 text-red-600', iconBg: 'bg-red-100', path: '/insurance' }] : []),
  ];

  const getStatusBadge = (status) => {
    const styles = {
      scheduled: 'bg-emerald-50 text-emerald-700 border-emerald-200',
      pending_verification: 'bg-amber-50 text-amber-700 border-amber-200',
      completed: 'bg-gray-100 text-gray-600 border-gray-200',
      cancelled: 'bg-red-50 text-red-600 border-red-200',
    };
    return styles[status] || 'bg-gray-100 text-gray-600';
  };

  const formatDuration = (seconds) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-3 border-teal-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Overview of your dental practice</p>
      </div>

      {/* Pending Alerts */}
      {pendingNotifications.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-5 h-5 text-amber-600" />
            <h3 className="text-sm font-semibold text-amber-800">
              {pendingNotifications.length} Appointment{pendingNotifications.length > 1 ? 's' : ''} Pending Verification
            </h3>
          </div>
          <p className="text-xs text-amber-700 mb-3">Review and confirm AI-scheduled appointments</p>
          <Button
            size="sm"
            variant="outline"
            className="border-amber-300 text-amber-700 hover:bg-amber-100"
            onClick={() => navigate('/appointments')}
          >
            Review Now <ArrowRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      )}

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat) => {
          const Icon = stat.icon;
          return (
            <Card 
              key={stat.label} 
              className="border-gray-200/80 hover:shadow-md hover:border-teal-300 transition-all cursor-pointer"
              onClick={() => navigate(stat.path)}
            >
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{stat.label}</p>
                    <p className="text-3xl font-bold text-gray-900 mt-1">{stat.value}</p>
                  </div>
                  <div className={`w-11 h-11 rounded-xl ${stat.iconBg} flex items-center justify-center`}>
                    <Icon className={`w-5 h-5 ${stat.color.split(' ')[1]}`} />
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Live Calls Section - Show if any active */}
      {activeCalls.length > 0 && (
        <Card className="border-green-200/80 bg-gradient-to-br from-green-50/50 to-white">
          <CardHeader className="border-b border-green-100 pb-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Phone className="w-5 h-5 text-green-600" />
                  <span className="absolute -top-1 -right-1 w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                </div>
                <CardTitle className="text-base font-semibold text-green-900">
                  Live Call{activeCalls.length > 1 ? 's' : ''} in Progress
                </CardTitle>
                <Badge className="bg-green-500 text-white text-xs animate-pulse">
                  {activeCalls.length} ACTIVE
                </Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-4">
            <div className="space-y-2">
              {activeCalls.map((call) => (
                <div key={call.id || call.call_id} className="flex items-center justify-between p-3 bg-white rounded-lg border border-green-200 hover:border-green-300 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="relative">
                      <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
                        <Phone className="w-5 h-5 text-green-600" />
                      </div>
                      <span className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full animate-ping"></span>
                      <span className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full"></span>
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-gray-900">
                        {call.patient_name || call.from_number || 'Unknown Caller'}
                      </p>
                      <p className="text-xs text-gray-500 flex items-center gap-1">
                        <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                        Started {new Date(call.created_at || Date.now()).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className="bg-green-100 text-green-700 text-xs font-semibold">
                      AI HANDLING
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Appointments */}
        <Card className="border-gray-200/80">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Upcoming Appointments</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => navigate('/appointments')} className="text-teal-600 hover:text-teal-700">
                View All <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {recentAppointments.map((apt) => (
              <div key={apt.id} className="flex items-center justify-between p-3 rounded-lg bg-gray-50/80 hover:bg-gray-100/80 transition-colors">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-full bg-teal-100 flex items-center justify-center shrink-0">
                    <span className="text-xs font-semibold text-teal-700">{apt.patient_name?.charAt(0)}</span>
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{apt.patient_name}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <Clock className="w-3 h-3 text-gray-400" />
                      <span className="text-xs text-gray-500">{apt.appointment_date} at {apt.appointment_time}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {apt.is_emergency && <Badge variant="destructive" className="text-[10px]">URGENT</Badge>}
                  <div className={`text-[10px] px-2 py-1 rounded-md border ${getStatusBadge(apt.status)}`}>
                    {apt.status === 'pending_verification' ? 'Pending' : apt.status}
                  </div>
                </div>
              </div>
            ))}
            {recentAppointments.length === 0 && (
              <p className="text-sm text-gray-500 text-center py-8">No upcoming appointments</p>
            )}
          </CardContent>
        </Card>

        {/* Recent Calls */}
        <Card className="border-gray-200/80">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Recent AI Calls</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => navigate('/call-logs')} className="text-teal-600 hover:text-teal-700">
                View All <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            {recentCalls.map((call) => (
              <div key={call.id} className="p-3 rounded-lg bg-gray-50/80 hover:bg-gray-100/80 transition-colors">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <PhoneIncoming className="w-4 h-4 text-teal-500" />
                    <span className="text-sm font-medium text-gray-900">{call.patient_name || 'Unknown Caller'}</span>
                  </div>
                  <span className="text-xs text-gray-400">{call.duration_seconds ? formatDuration(call.duration_seconds) : '--:--'}</span>
                </div>
                <p className="text-xs text-gray-500 line-clamp-1">
                  {call.call_summary?.reason || call.action_taken || 'General inquiry'}
                </p>
              </div>
            ))}
            {recentCalls.length === 0 && (
              <p className="text-sm text-gray-500 text-center py-8">No recent calls</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
