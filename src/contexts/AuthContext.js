import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const AuthContext = createContext(null);
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const TOKEN_KEY = 'dental_token';
const SUPER_TOKEN_KEY = 'dental_token_super'; // saved while impersonating

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [practice, setPractice] = useState(null);
  const [token, setToken] = useState(localStorage.getItem(TOKEN_KEY));
  const [loading, setLoading] = useState(true);

  const axiosAuth = useCallback(() => {
    return axios.create({
      baseURL: API,
      headers: { Authorization: `Bearer ${token}` }
    });
  }, [token]);

  const fetchPractice = useCallback(async (pid, tok) => {
    try {
      const res = await axios.get(`${API}/practice/${pid}/config`, {
        headers: { Authorization: `Bearer ${tok}` }
      });
      setPractice(res.data);
      return res.data;
    } catch {
      setPractice(null);
      return null;
    }
  }, []);

  useEffect(() => {
    if (token) {
      axios.get(`${API}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      })
        .then(async res => {
          setUser(res.data);
          if (res.data?.practice_id) {
            await fetchPractice(res.data.practice_id, token);
          }
          setLoading(false);
        })
        .catch(() => {
          localStorage.removeItem(TOKEN_KEY);
          setToken(null); setUser(null); setPractice(null); setLoading(false);
        });
    } else {
      setLoading(false);
    }
  }, [token, fetchPractice]);

  const login = async (email, password) => {
    const res = await axios.post(`${API}/auth/login`, { email, password });
    const { access_token, user: userData } = res.data;
    // Login as a fresh user clears any leftover impersonation state
    localStorage.removeItem(SUPER_TOKEN_KEY);
    localStorage.setItem(TOKEN_KEY, access_token);
    setToken(access_token); setUser(userData);
    if (userData?.practice_id) await fetchPractice(userData.practice_id, access_token);
    return userData;
  };

  const register = async (email, password, full_name, practice_name) => {
    const res = await axios.post(`${API}/auth/register`, { email, password, full_name, practice_name });
    const { access_token, user: userData } = res.data;
    localStorage.setItem(TOKEN_KEY, access_token);
    setToken(access_token); setUser(userData);
    if (userData?.practice_id) await fetchPractice(userData.practice_id, access_token);
    return userData;
  };

  const onboardPractice = async (payload) => {
    const res = await axios.post(`${API}/onboarding/practice`, payload);
    const { access_token, practice_id } = res.data;
    localStorage.setItem(TOKEN_KEY, access_token);
    setToken(access_token);
    const me = await axios.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${access_token}` } });
    setUser(me.data);
    await fetchPractice(practice_id, access_token);
    return res.data;
  };

  const completeOnboarding = async (practice_id) => {
    await axios.post(`${API}/onboarding/${practice_id}/complete`);
    if (token) await fetchPractice(practice_id, token);
  };

  /**
   * Super-admin only: drop into a practice's UI as one of its admins.
   * Saves the original super-admin token so it can be restored via
   * exitImpersonation().
   */
  const startImpersonation = async (practiceId) => {
    const res = await axios.post(`${API}/superadmin/practices/${practiceId}/impersonate`, {}, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const { access_token } = res.data;
    // Stash the super-admin token so we can swap back on exit
    localStorage.setItem(SUPER_TOKEN_KEY, token);
    localStorage.setItem(TOKEN_KEY, access_token);
    // Clear user/practice synchronously so any in-flight super-admin
    // requests from the previous page don't race the token swap and
    // hit 403s on now-forbidden endpoints.
    setUser(null);
    setPractice(null);
    setToken(access_token);
    const me = await axios.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${access_token}` } });
    setUser(me.data);
    if (me.data?.practice_id) await fetchPractice(me.data.practice_id, access_token);
    return res.data;
  };

  const exitImpersonation = async () => {
    const superToken = localStorage.getItem(SUPER_TOKEN_KEY);
    if (!superToken) return null;
    localStorage.setItem(TOKEN_KEY, superToken);
    localStorage.removeItem(SUPER_TOKEN_KEY);
    setToken(superToken);
    setPractice(null);
    const me = await axios.get(`${API}/auth/me`, { headers: { Authorization: `Bearer ${superToken}` } });
    setUser(me.data);
    return me.data;
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(SUPER_TOKEN_KEY);
    setToken(null); setUser(null); setPractice(null);
  };

  const updateUser = (userData) => setUser(prev => ({ ...prev, ...userData }));
  const refreshPractice = () => user?.practice_id && fetchPractice(user.practice_id, token);

  // Role checks — when impersonating, the active role is the practice
  // admin's, not the super_admin's. isSuperAdmin reflects the *current*
  // session, so impersonation correctly hides the Platform Console.
  const isImpersonating = !!user?.impersonated_by;
  const isSuperAdmin = user?.role === 'super_admin' && !isImpersonating;
  const isAdmin = user?.role === 'admin' || isSuperAdmin;
  const isStaff = ['admin', 'staff', 'super_admin'].includes(user?.role);
  const isProvider = user?.role === 'provider';
  const isAuditor = user?.role === 'auditor';
  const canManagePractice = isAdmin;
  const canManageInsurance = isAdmin || isStaff;
  const canViewAudit = isAdmin || isAuditor;

  const needsOnboarding = practice?.settings ? practice?.status === 'onboarding' || practice?.name == null : false;

  return (
    <AuthContext.Provider value={{
      user, practice, token, loading,
      login, register, logout, updateUser, axiosAuth, API,
      onboardPractice, completeOnboarding, refreshPractice,
      startImpersonation, exitImpersonation, isImpersonating,
      isSuperAdmin, isAdmin, isStaff, isProvider, isAuditor,
      canManagePractice, canManageInsurance, canViewAudit,
      needsOnboarding
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
