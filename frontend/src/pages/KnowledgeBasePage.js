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
import { Plus, Edit2, Trash2, BookOpen, Loader2 } from 'lucide-react';

const CATEGORIES = ['Protocol', 'Insurance', 'FAQ', 'General'];

const CATEGORY_COLORS = {
  Protocol: 'bg-blue-50 text-blue-700',
  Insurance: 'bg-violet-50 text-violet-700',
  FAQ: 'bg-emerald-50 text-emerald-700',
  General: 'bg-gray-100 text-gray-600',
};

export default function KnowledgeBasePage() {
  const { has, featuresLoading } = useFeatures();
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialog, setDialog] = useState(false);
  const [editingDoc, setEditingDoc] = useState(null);
  const [form, setForm] = useState({ title: '', content: '', category: 'General' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (featuresLoading || !has('knowledge_base')) return;
    fetchDocs();
  }, [featuresLoading]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchDocs = async () => {
    try {
      const res = await api.get('/knowledge');
      setDocs(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  if (!featuresLoading && !has('knowledge_base')) {
    return (
      <FeatureUpgradeCard
        featureName="Knowledge Base"
        description="Train your AI on your practice's own protocols, insurance policies, and FAQs."
        bullets={[
          'Custom treatment protocols',
          'Insurance policy reference',
          'Practice-specific FAQ',
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

  const openAdd = () => {
    setEditingDoc(null);
    setForm({ title: '', content: '', category: 'General' });
    setError('');
    setDialog(true);
  };

  const openEdit = (doc) => {
    setEditingDoc(doc);
    setForm({ title: doc.title, content: doc.content, category: doc.category });
    setError('');
    setDialog(true);
  };

  const closeDialog = () => {
    setDialog(false);
    setError('');
  };

  const handleSave = async () => {
    if (!form.title.trim() || !form.content.trim()) {
      setError('Title and content are required.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      if (editingDoc) {
        await api.put(`/knowledge/${editingDoc.id}`, form);
      } else {
        await api.post('/knowledge', form);
      }
      await fetchDocs();
      setDialog(false);
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to save document.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (doc) => {
    if (!window.confirm(`Delete "${doc.title}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/knowledge/${doc.id}`);
      await fetchDocs();
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to delete document.');
    }
  };

  const formatDate = (dt) => {
    if (!dt) return '—';
    try {
      return new Date(dt).toLocaleDateString(undefined, {
        month: 'short', day: 'numeric', year: 'numeric',
      });
    } catch {
      return '—';
    }
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Knowledge Base</h1>
          <p className="text-sm text-gray-500 mt-1">
            Documents used to ground the AI receptionist's responses
          </p>
        </div>
        <Button className="bg-teal-600 hover:bg-teal-700" onClick={openAdd}>
          <Plus className="w-4 h-4 mr-1" /> Add Document
        </Button>
      </div>

      {docs.length === 0 ? (
        <Card className="border-gray-200/80">
          <CardContent className="p-10 text-center">
            <BookOpen className="w-10 h-10 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-500">No knowledge documents yet.</p>
            <p className="text-xs text-gray-400 mt-1">
              Add protocols, insurance information, and FAQs to help the AI answer accurately.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3">
          {docs.map((doc) => (
            <Card key={doc.id} className="border-gray-200/80 hover:shadow-sm transition-shadow">
              <CardContent className="p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <p className="text-sm font-semibold text-gray-900 truncate">{doc.title}</p>
                      <Badge
                        className={`text-[10px] shrink-0 ${CATEGORY_COLORS[doc.category] || CATEGORY_COLORS.General}`}
                      >
                        {doc.category}
                      </Badge>
                    </div>
                    <p className="text-xs text-gray-500 line-clamp-2">{doc.content}</p>
                    <p className="text-[11px] text-gray-400 mt-1.5">
                      Updated {formatDate(doc.updated_at)}
                    </p>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => openEdit(doc)}
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-red-500 hover:text-red-600"
                      onClick={() => handleDelete(doc)}
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
            <DialogTitle>{editingDoc ? 'Edit Document' : 'Add Document'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {error && (
              <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-600">
                {error}
              </div>
            )}
            <div className="space-y-1.5">
              <Label>Title *</Label>
              <Input
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                placeholder="e.g. Cleaning Protocol"
                maxLength={200}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Category</Label>
              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                className="w-full h-10 rounded-md border border-gray-200 bg-white px-3 text-sm"
              >
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Content *</Label>
              <Textarea
                value={form.content}
                onChange={(e) => setForm({ ...form, content: e.target.value })}
                placeholder="Enter the knowledge content here..."
                rows={8}
                maxLength={10000}
                className="resize-none text-sm"
              />
              <p className="text-[11px] text-gray-400 text-right">
                {form.content.length.toLocaleString()}/10,000
              </p>
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
              {editingDoc ? 'Save Changes' : 'Add Document'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
