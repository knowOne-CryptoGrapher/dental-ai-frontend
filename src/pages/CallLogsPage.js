import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import {
  Phone, PhoneIncoming, PhoneOff, Clock, Search,
  FileText, User, ChevronRight, AlertTriangle
} from 'lucide-react';
import { mockCallLogs } from '../data/mockData';

export default function CallLogsPage({ useMock = false }) {
  const { axiosAuth } = useAuth();
  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedCall, setSelectedCall] = useState(null);

  useEffect(() => { fetchCalls(); }, []);

  const fetchCalls = async () => {
    if (useMock) { setCalls(mockCallLogs); setLoading(false); return; }
    try {
      const api = axiosAuth();
      const res = await api.get('/call-logs');
      
      // Transform API response to match component expectations
      const transformedCalls = (res.data || []).map(call => ({
        id: call.call_id || `call-${Date.now()}`,
        patient_name: call.patient_name || 'Unknown Caller',
        patient_phone: call.from_number || 'N/A',
        duration: call.duration_seconds || 0,
        timestamp: call.created_at || new Date().toISOString(),
        status: call.call_status || 'completed',
        handled_by: call.agent_id || 'AI',
        transcript: call.transcript || 'No transcript available',
        action_taken: call.reason_for_call,
        call_summary: {
          reason: call.reason_for_call || 'General inquiry',
          notes: call.emergency_detected ? `⚠️ EMERGENCY: ${(call.emergency_keywords || []).join(', ')}` : null
        },
        emergency_detected: call.emergency_detected || false,
        emergency_keywords: call.emergency_keywords || []
      }));
      
      setCalls(transformedCalls);
    } catch (err) { 
      console.error('Failed to fetch calls:', err);
      setCalls([]); 
    } finally { 
      setLoading(false); 
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds || seconds === 0) return '0m 0s';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}m ${s}s`;
  };

  const formatTime = (timestamp) => {
    if (!timestamp) return '—';
    try {
      const d = new Date(timestamp);
      return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true });
    } catch { return '—'; }
  };

  const getStatusColor = (status) => {
    const s = (status || '').toLowerCase();
    if (s === 'active' || s === 'started') return 'bg-green-50 text-green-700 border-green-200';
    if (s === 'completed') return 'bg-gray-100 text-gray-600 border-gray-200';
    return 'bg-red-50 text-red-600 border-red-200';
  };

  const filtered = calls.filter(c => {
    if (!search || search.trim() === '') return true;
    const searchLower = search.toLowerCase();
    return (c.patient_name || '').toLowerCase().includes(searchLower) ||
           (c.patient_phone || '').includes(search) ||
           (c.call_summary?.reason || '').toLowerCase().includes(searchLower);
  });

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Call Logs</h1>
        <p className="text-sm text-gray-500 mt-1">{calls.length} total calls handled by AI</p>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <Input placeholder="Search calls..." value={search} onChange={e => setSearch(e.target.value)} className="pl-10" />
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" /></div>
      ) : (
        <div className="space-y-3">
          {filtered.map((call) => (
            <Card
              key={call.id}
              className="border-gray-200/80 hover:shadow-sm transition-all cursor-pointer"
              onClick={() => setSelectedCall(call)}
            >
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
                      call.emergency_detected ? 'bg-red-100' : call.status === 'completed' ? 'bg-green-100' : 'bg-gray-100'
                    }`}>
                      {call.emergency_detected
                        ? <AlertTriangle className="w-5 h-5 text-red-600" />
                        : call.status === 'completed'
                        ? <Phone className="w-5 h-5 text-green-600" />
                        : <PhoneIncoming className="w-5 h-5 text-gray-500" />
                      }
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold text-gray-900">
                          {call.patient_name || 'Unknown Caller'}
                        </p>
                        {call.emergency_detected && (
                          <Badge className="text-[10px] bg-red-100 text-red-700 border-red-200">
                            EMERGENCY
                          </Badge>
                        )}
                        <Badge variant="outline" className={`text-[10px] ${getStatusColor(call.status)}`}>
                          {call.status}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-xs text-gray-500 flex items-center gap-1">
                          <Phone className="w-3 h-3" />{call.patient_phone}
                        </span>
                        <span className="text-xs text-gray-400">·</span>
                        <span className="text-xs text-gray-500 flex items-center gap-1">
                          <Clock className="w-3 h-3" />{formatDuration(call.duration)}
                        </span>
                        <span className="text-xs text-gray-400">·</span>
                        <span className="text-xs text-gray-500">{formatTime(call.timestamp)}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {call.call_summary?.reason && (
                      <span className="hidden sm:block text-xs text-gray-500 bg-gray-50 px-2 py-1 rounded max-w-48 truncate">
                        {call.call_summary.reason}
                      </span>
                    )}
                    <ChevronRight className="w-4 h-4 text-gray-400" />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
          {filtered.length === 0 && <p className="text-sm text-gray-500 text-center py-12">No call logs found</p>}
        </div>
      )}

      {/* Call Detail Dialog */}
      <Dialog open={!!selectedCall} onOpenChange={() => setSelectedCall(null)}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          {selectedCall && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-teal-100 flex items-center justify-center">
                    <Phone className="w-5 h-5 text-teal-600" />
                  </div>
                  <div>
                    <p>{selectedCall.patient_name || 'Unknown Caller'}</p>
                    <p className="text-xs font-normal text-gray-500">{selectedCall.patient_phone} · {formatDuration(selectedCall.duration)}</p>
                  </div>
                </DialogTitle>
              </DialogHeader>

              <div className="space-y-4 mt-2">
                {/* Summary */}
                {selectedCall.call_summary && (
                  <div className="p-3 bg-teal-50/50 rounded-lg border border-teal-100">
                    <p className="text-xs font-medium text-teal-800 mb-2">Call Summary</p>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      {selectedCall.call_summary.reason && (
                        <div><span className="text-xs text-gray-500">Reason</span><p className="font-medium text-gray-800">{selectedCall.call_summary.reason}</p></div>
                      )}
                      {selectedCall.call_summary.appointment_time && (
                        <div><span className="text-xs text-gray-500">Appointment</span><p className="font-medium text-gray-800">{selectedCall.call_summary.appointment_time}</p></div>
                      )}
                      {selectedCall.call_summary.notes && (
                        <div className="col-span-2"><span className="text-xs text-gray-500">Notes</span><p className="text-gray-800">{selectedCall.call_summary.notes}</p></div>
                      )}
                    </div>
                  </div>
                )}

                {/* Transcript */}
                <div>
                  <p className="text-xs font-medium text-gray-500 mb-2 flex items-center gap-1">
                    <FileText className="w-3 h-3" /> Transcript
                  </p>
                  <div className="bg-gray-50 rounded-lg p-4 max-h-64 overflow-y-auto">
                    {selectedCall.transcript?.split('\n').map((line, i) => {
                      const isAI = line.startsWith('AI:');
                      const isCaller = line.startsWith('Caller:');
                      return (
                        <div key={i} className={`mb-2 ${isAI ? 'pl-0' : isCaller ? 'pl-4' : ''}`}>
                          {isAI && <span className="text-xs font-semibold text-teal-600">AI Assistant</span>}
                          {isCaller && <span className="text-xs font-semibold text-blue-600">Caller</span>}
                          <p className="text-sm text-gray-700">
                            {line.replace(/^(AI:|Caller:)\s*/, '')}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Metadata */}
                <div className="grid grid-cols-2 gap-3 text-sm border-t border-gray-100 pt-3">
                  <div><span className="text-xs text-gray-500">Status</span><p className="font-medium capitalize">{selectedCall.status}</p></div>
                  <div><span className="text-xs text-gray-500">Handled By</span><p className="font-medium uppercase">{selectedCall.handled_by}</p></div>
                  <div><span className="text-xs text-gray-500">Action Taken</span><p className="font-medium">{selectedCall.action_taken || '—'}</p></div>
                  <div><span className="text-xs text-gray-500">Time</span><p className="font-medium">{formatTime(selectedCall.timestamp)}</p></div>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
