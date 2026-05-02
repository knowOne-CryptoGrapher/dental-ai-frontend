import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { ShieldAlert, LogOut, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

/**
 * Persistent banner shown across every practice-portal page when a
 * super-admin is impersonating. Provides a one-click exit back to the
 * Platform Console.
 */
export default function ImpersonationBanner() {
  const { isImpersonating, user, exitImpersonation } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);

  if (!isImpersonating) return null;

  const onExit = async () => {
    setBusy(true);
    try {
      await exitImpersonation();
      toast.success('Exited impersonation');
      navigate('/admin/practices');
    } catch {
      toast.error('Failed to exit impersonation');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      data-testid="impersonation-banner"
      className="bg-gradient-to-r from-red-600 via-red-500 to-amber-500 text-white shadow-md"
    >
      <div className="max-w-7xl mx-auto px-4 py-2 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div className="flex items-center gap-2 text-sm">
          <ShieldAlert className="w-4 h-4 shrink-0" />
          <span className="font-semibold tracking-wide">SUPER ADMIN IMPERSONATION</span>
          <span className="opacity-90">— viewing as <strong>{user?.full_name || user?.email}</strong> at <strong>{user?.practice_name || 'this practice'}</strong></span>
          {user?.impersonator_email && (
            <span className="hidden sm:inline opacity-75">· logged as {user.impersonator_email}</span>
          )}
        </div>
        <button
          data-testid="exit-impersonation-btn"
          onClick={onExit}
          disabled={busy}
          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md bg-white/15 hover:bg-white/25 text-white text-xs font-semibold tracking-wider uppercase transition disabled:opacity-50"
        >
          {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <LogOut className="w-3.5 h-3.5" />}
          Exit impersonation
        </button>
      </div>
    </div>
  );
}
