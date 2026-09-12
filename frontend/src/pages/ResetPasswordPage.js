import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Loader2, ShieldCheck, AlertTriangle, CheckCircle2, Eye, EyeOff } from 'lucide-react';

const API_BASE = process.env.REACT_APP_API_URL || '';
const API = `${API_BASE}/api`;

export default function ResetPasswordPage() {
  const { token } = useParams();

  const [status, setStatus] = useState('loading'); // loading | valid | invalid | done
  const [email, setEmail] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const res = await axios.get(`${API}/auth/reset-password/${token}`);
        setEmail(res.data.email);
        setStatus('valid');
      } catch (err) {
        const detail = err.response?.data?.detail || 'This reset link is invalid or has expired.';
        setErrorMsg(detail);
        setStatus('invalid');
      }
    })();
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');

    if (password.length < 8) { setFormError('Password must be at least 8 characters.'); return; }
    if (password !== confirmPassword) { setFormError('Passwords do not match.'); return; }

    setSubmitting(true);
    try {
      await axios.post(`${API}/auth/reset-password/${token}`, { new_password: password });
      setStatus('done');
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Failed to reset password. Please try again.');
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
            <h2 className="text-lg font-semibold text-gray-900">Reset Link Invalid</h2>
            <p className="text-sm text-gray-600">{errorMsg}</p>
            <a href="/forgot-password" className="text-teal-600 text-sm underline">Request a new reset link</a>
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
            <h2 className="text-lg font-semibold text-gray-900">Password Reset</h2>
            <p className="text-sm text-gray-600">
              Your password has been changed. Please sign in with your new password.
            </p>
            <a href="/login" className="text-teal-600 text-sm underline">Go to sign in</a>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-6">
        {/* Header */}
        <div className="text-center space-y-1">
          <div className="flex items-center justify-center gap-2 mb-3">
            <ShieldCheck className="w-7 h-7 text-teal-600" />
            <span className="text-xl font-bold text-gray-900">Front Desk Dental AI</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Reset your password</h1>
          <p className="text-sm text-gray-500">
            Choose a new password for <strong>{email}</strong>
          </p>
        </div>

        {/* Reset form */}
        <Card className="border-gray-200">
          <CardContent className="p-6">
            <form onSubmit={handleSubmit} className="space-y-4">
              {formError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                  {formError}
                </div>
              )}

              <div className="space-y-1.5">
                <Label htmlFor="password">New Password</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 8 characters"
                    required
                  />
                  <button
                    type="button"
                    className="absolute right-2 top-2 text-gray-500"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? <EyeOff /> : <Eye />}
                  </button>
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="confirmPassword">Confirm New Password</Label>
                <Input
                  id="confirmPassword"
                  type={showPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repeat your new password"
                  required
                />
              </div>

              <Button
                type="submit"
                className="w-full bg-teal-600 hover:bg-teal-700"
                disabled={submitting}
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Resetting…
                  </>
                ) : (
                  'Reset Password'
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-xs text-gray-400">
          Remembered your password?{' '}
          <a href="/login" className="text-teal-600 underline">Sign in</a>
        </p>
      </div>
    </div>
  );
}
