import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { TERMS_VERSION, PRIVACY_POLICY_VERSION } from '../config/legal';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Loader2, ShieldCheck, AlertTriangle, CheckCircle2 } from 'lucide-react';

const API_BASE = process.env.REACT_APP_API_URL || '';
const API = `${API_BASE}/api`;

const ROLE_LABELS = {
  staff: 'Staff',
  provider: 'Provider',
  auditor: 'Auditor',
};

const ROLE_COLORS = {
  staff: 'bg-teal-100 text-teal-700',
  provider: 'bg-blue-100 text-blue-700',
  auditor: 'bg-amber-100 text-amber-700',
};

export default function InvitePage() {
  const { token } = useParams();

  const [status, setStatus] = useState('loading'); // loading | valid | invalid | done
  const [invite, setInvite] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');

  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [acceptedPrivacy, setAcceptedPrivacy] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const res = await axios.get(`${API}/invite/${token}`);
        setInvite(res.data);
        setStatus('valid');
      } catch (err) {
        const detail = err.response?.data?.detail || 'This invite link is invalid or has expired.';
        setErrorMsg(detail);
        setStatus('invalid');
      }
    })();
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');

    if (!fullName.trim()) { setFormError('Full name is required.'); return; }
    if (password.length < 8) { setFormError('Password must be at least 8 characters.'); return; }
    if (password !== confirmPassword) { setFormError('Passwords do not match.'); return; }
    if (!acceptedTerms || !acceptedPrivacy) {
      setFormError('You must accept the Terms of Service and Privacy Policy to continue.');
      return;
    }

    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/invite/${token}/complete`, {
        full_name: fullName.trim(),
        password,
        accepted_terms_version: TERMS_VERSION,
        accepted_privacy_version: PRIVACY_POLICY_VERSION,
      });

      localStorage.setItem('dental_token', res.data.access_token);
      setStatus('done');
      // Full reload so AuthContext re-initialises with the new token
      setTimeout(() => { window.location.replace('/dashboard'); }, 1500);
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Failed to create account. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-teal-600 animate-spin" />
      </div>
    );
  }

  if (status === 'invalid') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="max-w-md w-full border-red-200">
          <CardContent className="p-8 text-center space-y-3">
            <AlertTriangle className="w-12 h-12 text-red-500 mx-auto" />
            <h2 className="text-lg font-semibold text-gray-900">Invite Link Invalid</h2>
            <p className="text-sm text-gray-600">{errorMsg}</p>
            <p className="text-xs text-gray-400">
              Contact your practice administrator to request a new invite.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === 'done') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
        <Card className="max-w-md w-full border-teal-200">
          <CardContent className="p-8 text-center space-y-3">
            <CheckCircle2 className="w-12 h-12 text-teal-600 mx-auto" />
            <h2 className="text-lg font-semibold text-gray-900">Account Created!</h2>
            <p className="text-sm text-gray-600">Redirecting to your dashboard…</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const roleColor = ROLE_COLORS[invite.role] || 'bg-gray-100 text-gray-600';
  const roleLabel = ROLE_LABELS[invite.role] || invite.role;

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6">
        {/* Header */}
        <div className="text-center space-y-1">
          <div className="flex items-center justify-center gap-2 mb-3">
            <ShieldCheck className="w-7 h-7 text-teal-600" />
            <span className="text-xl font-bold text-gray-900">FrontDesk Dental AI</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">You've been invited</h1>
          <p className="text-sm text-gray-500">
            Complete your account setup to join <strong>{invite.practice_name}</strong>
          </p>
        </div>

        {/* Invite summary */}
        <Card className="border-gray-200">
          <CardContent className="p-4 space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Practice</span>
              <span className="font-medium text-gray-900">{invite.practice_name}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Email</span>
              <span className="font-medium text-gray-900">{invite.email}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500">Role</span>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${roleColor}`}>
                {roleLabel}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Signup form */}
        <Card className="border-gray-200">
          <CardContent className="p-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              {formError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                  {formError}
                </div>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="fullName">Full Name</Label>
                <Input
                  id="fullName"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Your full name"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  value={invite.email}
                  readOnly
                  className="bg-gray-50 text-gray-500 cursor-not-allowed"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="confirmPassword">Confirm Password</Label>
                <Input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repeat your password"
                  required
                />
              </div>

              <div className="space-y-3 pt-1">
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={acceptedTerms}
                    onChange={(e) => setAcceptedTerms(e.target.checked)}
                    className="mt-0.5 rounded"
                  />
                  <span className="text-xs text-gray-600">
                    I have read and agree to the{' '}
                    <a
                      href="/terms"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-teal-600 underline"
                    >
                      Terms of Service
                    </a>{' '}
                    (v{TERMS_VERSION})
                  </span>
                </label>

                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={acceptedPrivacy}
                    onChange={(e) => setAcceptedPrivacy(e.target.checked)}
                    className="mt-0.5 rounded"
                  />
                  <span className="text-xs text-gray-600">
                    I have read and agree to the{' '}
                    <a
                      href="/privacy"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-teal-600 underline"
                    >
                      Privacy Policy
                    </a>{' '}
                    (v{PRIVACY_POLICY_VERSION})
                  </span>
                </label>
              </div>

              <Button
                type="submit"
                className="w-full bg-teal-600 hover:bg-teal-700"
                disabled={submitting}
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Creating account…
                  </>
                ) : (
                  'Create Account'
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-gray-400">
          Already have an account?{' '}
          <a href="/login" className="text-teal-600 underline">Sign in</a>
        </p>
      </div>
    </div>
  );
}
