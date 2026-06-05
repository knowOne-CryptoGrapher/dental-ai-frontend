import React, { useState, useEffect } from 'react';
import { api } from '../config/api';
import { useFeatures } from '../hooks/useFeatures';
import FeatureUpgradeCard from '../components/FeatureUpgradeCard';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../components/ui/dialog';
import { Plus, Edit2, Trash2, GitBranch, Loader2 } from 'lucide-react';

export default function RoutingRulesPage() {
  const { has, featuresLoading } = useFeatures();
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [form, setForm] = useState({ name: '', condition: '', action: '', priority: 1 });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (featuresLoading || !has('custom_routing_rules')) return;
    fetchRules();
  }, [featuresLoading]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchRules = async () => {
    try {
      const res = await api.get('/routing-rules?all=true');
      setRules(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (!featuresLoading && !has('custom_routing_rules')) {
    return (
      <FeatureUpgradeCard
        featureName="Custom Routing Rules"
        description="Define how your AI handles specific patient scenarios — route emergencies, escalate complex cases, customize call flow."
        bullets={[
          'Emergency escalation rules',
          'Complex case routing',
          'Custom call flow logic',
        ]}
        requiredTier="Enterprise"
        ctaLabel="Upgrade to Enterprise"
      />
    );
  }

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="w-6 h-6 border-2 border-teal-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const nextPriority = rules.length > 0 ? Math.max(...rules.map(r => r.priority)) + 1 : 1;

  const openAdd = () => {
    setEditingRule(null);
    setForm({ name: '', condition: '', action: '', priority: nextPriority });
    setError('');
    setDialog(true);
  };

  const openEdit = (rule) => {
    setEditingRule(rule);
    setForm({
      name: rule.name,
      condition: rule.condition,
      action: rule.action,
      priority: rule.priority,
    });
    setError('');
    setDialog(true);
  };

  const closeDialog = () => {
    setDialog(false);
    setError('');
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.condition.trim() || !form.action.trim()) {
      setError('Name, condition, and action are required.');
      return;
    }
    const priority = parseInt(form.priority, 10);
    if (isNaN(priority) || priority < 1) {
      setError('Priority must be a positive integer.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      if (editingRule) {
        await api.put(`/routing-rules/${editingRule.id}`, { ...form, priority });
      } else {
        await api.post('/routing-rules', { ...form, priority });
      }
      await fetchRules();
      setDialog(false);
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to save rule.');
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (rule) => {
    try {
      await api.put(`/routing-rules/${rule.id}`, { enabled: !rule.enabled });
      await fetchRules();
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to update rule.');
    }
  };

  const handleDelete = async (rule) => {
    if (!window.confirm(`Delete "${rule.name}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/routing-rules/${rule.id}`);
      await fetchRules();
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to delete rule.');
    }
  };

  const sortedRules = [...rules].sort((a, b) => a.priority - b.priority);

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Routing Rules</h1>
          <p className="text-sm text-gray-500 mt-1">
            Custom rules that guide the AI receptionist's call handling decisions
          </p>
        </div>
        <Button className="bg-teal-600 hover:bg-teal-700" onClick={openAdd}>
          <Plus className="w-4 h-4 mr-1" /> Add Rule
        </Button>
      </div>

      {sortedRules.length === 0 ? (
        <Card className="border-gray-200/80">
          <CardContent className="p-10 text-center">
            <GitBranch className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-500">No routing rules yet.</p>
            <p className="text-xs text-gray-400 mt-1">
              Add rules to control how the AI handles calls — emergencies, transfers, escalations, and more.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3">
          {sortedRules.map((rule) => (
            <Card
              key={rule.id}
              className={`border-gray-200/80 hover:shadow-sm transition-shadow ${!rule.enabled ? 'opacity-60' : ''}`}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <Badge className="bg-teal-50 text-teal-700 text-[10px] shrink-0 font-mono">
                        #{rule.priority}
                      </Badge>
                      <p className="text-sm font-semibold text-gray-900 truncate">{rule.name}</p>
                      {!rule.enabled && (
                        <Badge className="bg-gray-100 text-gray-500 text-[10px] shrink-0">
                          Disabled
                        </Badge>
                      )}
                    </div>
                    <div className="space-y-1">
                      <p className="text-xs text-gray-500">
                        <span className="font-medium text-gray-700">If:</span> {rule.condition}
                      </p>
                      <p className="text-xs text-gray-500">
                        <span className="font-medium text-gray-700">Then:</span> {rule.action}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={() => handleToggle(rule)}
                      title={rule.enabled ? 'Disable rule' : 'Enable rule'}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none
                        ${rule.enabled ? 'bg-teal-500' : 'bg-gray-300'}`}
                    >
                      <span
                        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform
                          ${rule.enabled ? 'translate-x-4' : 'translate-x-1'}`}
                      />
                    </button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => openEdit(rule)}
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-red-500 hover:text-red-600"
                      onClick={() => handleDelete(rule)}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={dialog} onOpenChange={(open) => { if (!open) closeDialog(); }}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingRule ? 'Edit Rule' : 'Add Rule'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {error && (
              <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-600">
                {error}
              </div>
            )}
            <div className="space-y-1.5">
              <Label>Name *</Label>
              <Input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Emergency escalation"
                maxLength={100}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Priority *</Label>
              <Input
                type="number"
                min={1}
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: e.target.value })}
                placeholder="1"
                className="w-28"
              />
              <p className="text-[11px] text-gray-400">Lower number = evaluated first</p>
            </div>
            <div className="space-y-1.5">
              <Label>Condition *</Label>
              <Textarea
                value={form.condition}
                onChange={(e) => setForm({ ...form, condition: e.target.value })}
                placeholder="e.g. caller mentions severe pain, swelling, or dental emergency"
                rows={3}
                maxLength={500}
                className="resize-none text-sm"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Action *</Label>
              <Textarea
                value={form.action}
                onChange={(e) => setForm({ ...form, action: e.target.value })}
                placeholder="e.g. immediately offer same-day emergency appointment and provide on-call number"
                rows={3}
                maxLength={500}
                className="resize-none text-sm"
              />
            </div>
          </div>
          <DialogFooter className="mt-2">
            <Button variant="outline" onClick={closeDialog}>
              Cancel
            </Button>
            <Button
              className="bg-teal-600 hover:bg-teal-700"
              onClick={handleSave}
              disabled={saving}
            >
              {saving && <Loader2 className="w-4 h-4 mr-1 animate-spin" />}
              {editingRule ? 'Save Changes' : 'Add Rule'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
