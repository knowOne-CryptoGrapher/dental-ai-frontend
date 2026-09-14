import React, { useState } from 'react';
import axios from 'axios';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Stethoscope, Loader2, CheckCircle2 } from 'lucide-react';

const API_BASE = process.env.REACT_APP_API_URL || '';
const API = `${API_BASE}/api`;

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await axios.post(`${API}/auth/request-password-reset`, { email });
    } catch {
      // Intentionally ignored — the confirmation below is shown regardless
      // of outcome, so this page never reveals whether the account exists
      // (mirrors the backend's own uniform response).
    } finally {
      setSubmitting(false);
      setSubmitted(true);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <Card className="w-full max-w-md shadow-lg">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Stethoscope className="w-6 h-6 text-blue-600" />
            Front Desk Dental AI
          </CardTitle>
          <CardDescription>Reset your password</CardDescription>
        </CardHeader>

        <CardContent>
          {submitted ? (
            <div className="text-center space-y-3 py-2">
              <CheckCircle2 className="w-10 h-10 text-teal-600 mx-auto" />
              <p className="text-sm text-gray-700">
                If an account with that email exists, we've sent a password reset link. Check your inbox.
              </p>
              <a href="/login" className="text-teal-600 text-sm underline block">Back to sign in</a>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <Label>Email</Label>
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              </div>

              <Button type="submit" className="w-full" disabled={submitting}>
                {submitting ? <Loader2 className="animate-spin" /> : 'Send Reset Link'}
              </Button>

              <a href="/login" className="text-blue-600 text-sm underline w-full text-center block">
                Back to sign in
              </a>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
