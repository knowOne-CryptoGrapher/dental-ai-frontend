import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { RefreshCw, FileText, Shield } from 'lucide-react';

export default function AuditPage() {
  const { axiosAuth, canViewAudit } = useAuth();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => { if (canViewAudit) fetchLogs(); else setLoading(false); }, [canViewAudit]);

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const api = axiosAuth();
      const res = await api.get('/audit-logs?limit=50');
      setLogs(res.data.logs || []);
    } catch (e) { console.error(e); } finally { setLoading(false); }
  };

  const formatTime = (ts) => {
    if (!ts) return '—';
    try { return new Date(ts).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }); } catch { return '—'; }
  };

  const actionColors = {
    patient_created: 'bg-emerald-50 text-emerald-700',
    patient_deleted: 'bg-red-50 text-red-700',
    appointment_created: 'bg-blue-50 text-blue-700',
    appointment_cancelled: 'bg-red-50 text-red-700',
    user_invited: 'bg-violet-50 text-violet-700',
    location_created: 'bg-cyan-50 text-cyan-700',
    provider_created: 'bg-indigo-50 text-indigo-700',
    claim_submitted: 'bg-amber-50 text-amber-700',
    eligibility_checked: 'bg-teal-50 text-teal-700',
    user_role_updated: 'bg-orange-50 text-orange-700',
  };

  if (!canViewAudit) {
    return (
      <div className="flex items-center justify-center h-96">
        <Card className="border-amber-200/80 bg-amber-50/50 max-w-md">
          <CardContent className="p-6 text-center">
            <Shield className="w-12 h-12 text-amber-600 mx-auto mb-3" />
            <h3 className="text-lg font-semibold text-gray-900 mb-1">Access Restricted</h3>
            <p className="text-sm text-gray-600">Only administrators and auditors can view audit logs.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Logs</h1>
          <p className="text-sm text-gray-500 mt-1">Compliance tracking for all actions</p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchLogs}><RefreshCw className="w-3.5 h-3.5 mr-1" /> Refresh</Button>
      </div>

      <Card className="border-gray-200/80">
        <CardContent className="p-0">
          {loading ? (
            <div className="flex justify-center py-12"><div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" /></div>
          ) : logs.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-12">No audit logs yet</p>
          ) : (
            <div className="divide-y divide-gray-100">
              {logs.map(log => (
                <div key={log.id} className="flex items-center justify-between px-4 py-3 hover:bg-gray-50/50 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center">
                      <Shield className="w-4 h-4 text-gray-500" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge className={`text-[10px] ${actionColors[log.action] || 'bg-gray-100 text-gray-600'}`}>
                          {log.action?.replace(/_/g, ' ')}
                        </Badge>
                        <span className="text-xs text-gray-400">{log.resource_type}</span>
                      </div>
                      <p className="text-xs text-gray-600 mt-0.5">
                        {log.details?.patient_name || log.details?.email || log.details?.name || log.resource_id?.slice(0, 8) || '—'}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-gray-500">{formatTime(log.timestamp)}</p>
                    {log.ip_address && <p className="text-[10px] text-gray-400">{log.ip_address}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
