import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  LayoutDashboard, Users, Calendar as CalendarIcon, Phone, BarChart3, Settings,
  LogOut, Bell, Menu, Stethoscope, Building2, UserCog, Shield,
  FileText, CreditCard, MapPin, Briefcase
} from 'lucide-react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import ImpersonationBanner from './ImpersonationBanner';
import { useFeatures } from '../hooks/useFeatures';

export default function Layout({ children, notifications = [], onNotificationRead }) {
  const { user, logout, isAdmin, isProvider, isAuditor, canViewAudit } = useAuth();
  const { has, plan_name, billing_status } = useFeatures();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [notifOpen, setNotifOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const unreadCount = notifications.filter(n => n.status === 'unread').length;

  const navItems = useMemo(() => {
    const items = [];

    // Common pages
    items.push({ path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, section: 'Main' });

    // Staff & Admin
    if (!isAuditor) {
      items.push(
        { path: '/patients', label: 'Patients', icon: Users, section: 'Main' },
        { path: '/appointments', label: 'Appointments', icon: CalendarIcon, section: 'Main' },
        { path: '/calendar', label: 'Calendar', icon: CalendarIcon, section: 'Main' },
        { path: '/call-logs', label: 'Call Logs', icon: Phone, section: 'Main' },
      );
    }

    // Insurance (admin/staff) — gated by plan feature
    if ((isAdmin || !isAuditor) && has('insurance')) {
      items.push({ path: '/insurance', label: 'Insurance', icon: FileText, section: 'Main' });
    }

    // Analytics — gated by plan feature
    if (has('analytics')) {
      items.push({ path: '/analytics', label: 'Analytics', icon: BarChart3, section: 'Main' });
    }

    // Admin: Practice Management
    if (isAdmin) {
      items.push(
        { path: '/manage', label: 'Manage Practice', icon: Building2, section: 'Practice' },
        { path: '/practice-settings', label: 'Practice Settings', icon: Settings, section: 'Practice' },
        { path: '/billing', label: 'Billing', icon: CreditCard, section: 'Practice' },
      );
    }

    // Audit (admin/auditor) — gated by plan feature
    if (canViewAudit && has('audit_log')) {
      items.push({ path: '/audit', label: 'Audit Logs', icon: Shield, section: 'Compliance' });
    }

    // Settings
    items.push({ path: '/settings', label: 'Settings', icon: Settings, section: 'Settings' });

    // Auditor-only pages
    if (isAuditor) {
      items.push(
        { path: '/patients', label: 'Patients', icon: Users, section: 'Read-Only' },
        { path: '/appointments', label: 'Appointments', icon: CalendarIcon, section: 'Read-Only' },
        { path: '/calendar', label: 'Calendar', icon: CalendarIcon, section: 'Read-Only' },
        { path: '/call-logs', label: 'Call Logs', icon: Phone, section: 'Read-Only' },
      );
    }

    return items;
  }, [isAdmin, isAuditor, canViewAudit, has]);

  useEffect(() => { setMobileOpen(false); }, [location.pathname]);

  const roleLabel = {
    super_admin: 'Super Admin',
    admin: 'Admin',
    staff: 'Staff',
    provider: 'Provider',
    auditor: 'Auditor',
  };

  const roleBadgeColor = {
    super_admin: 'bg-red-100 text-red-700',
    admin: 'bg-violet-100 text-violet-700',
    staff: 'bg-teal-100 text-teal-700',
    provider: 'bg-blue-100 text-blue-700',
    auditor: 'bg-amber-100 text-amber-700',
  };

  // Group nav items by section
  const sections = {};
  navItems.forEach(item => {
    if (!sections[item.section]) sections[item.section] = [];
    sections[item.section].push(item);
  });

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {mobileOpen && <div className="fixed inset-0 bg-black/40 z-40 lg:hidden" onClick={() => setMobileOpen(false)} />}

      {/* Sidebar */}
      <aside className={`
        fixed lg:static inset-y-0 left-0 z-50 flex flex-col
        bg-white border-r border-gray-200 transition-all duration-300
        ${sidebarOpen ? 'w-60' : 'w-[68px]'}
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        <div className="flex items-center gap-3 px-4 h-14 border-b border-gray-100 shrink-0">
          <div className="w-8 h-8 rounded-lg bg-teal-600 flex items-center justify-center shrink-0">
            <Stethoscope className="w-4 h-4 text-white" />
          </div>
          {sidebarOpen && (
            <div className="overflow-hidden">
              <h1 className="text-sm font-bold text-gray-900 truncate">DentalAI</h1>
              <p className="text-[9px] text-gray-400 truncate">Enterprise Platform</p>
            </div>
          )}
        </div>

        <nav className="flex-1 py-2 px-2 overflow-y-auto space-y-0.5">
          {Object.entries(sections).map(([section, items]) => (
            <div key={section}>
              {sidebarOpen && section !== 'Main' && (
                <p className="text-[9px] font-semibold text-gray-400 uppercase tracking-wider px-3 pt-3 pb-1">{section}</p>
              )}
              {!sidebarOpen && section !== 'Main' && <div className="border-t border-gray-100 my-1" />}
              {items.map(item => {
                const isActive = location.pathname === item.path;
                const Icon = item.icon;
                return (
                  <button
                    key={item.path + item.label}
                    onClick={() => navigate(item.path)}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium transition-colors
                      ${isActive ? 'bg-teal-50 text-teal-700' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'}`}
                  >
                    <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-teal-600' : 'text-gray-400'}`} />
                    {sidebarOpen && <span className="truncate">{item.label}</span>}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="p-2 border-t border-gray-100">
          {sidebarOpen && (
            <div className="px-3 py-2 mb-1">
              <p className="text-xs font-medium text-gray-900 truncate">{user?.full_name}</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full ${roleBadgeColor[user?.role] || 'bg-gray-100 text-gray-600'}`}>
                  {roleLabel[user?.role] || user?.role}
                </span>
              </div>
            </div>
          )}
          <button
            onClick={() => { logout(); navigate('/login'); }}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium text-gray-600 hover:bg-red-50 hover:text-red-600 transition-colors"
          >
            <LogOut className="w-4 h-4 shrink-0" />
            {sidebarOpen && <span>Sign Out</span>}
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <ImpersonationBanner />
        <header className="h-14 bg-white border-b border-gray-200 flex items-center justify-between px-4 lg:px-6 shrink-0">
          <div className="flex items-center gap-3">
            <button onClick={() => setMobileOpen(true)} className="lg:hidden p-2 rounded-lg hover:bg-gray-100">
              <Menu className="w-5 h-5 text-gray-600" />
            </button>
            <button onClick={() => setSidebarOpen(!sidebarOpen)} className="hidden lg:flex p-2 rounded-lg hover:bg-gray-100">
              <Menu className="w-5 h-5 text-gray-600" />
            </button>
            <div className="hidden sm:block">
              <h2 className="text-sm font-semibold text-gray-900">{user?.practice_name || 'Platform'}</h2>
              <p className="text-[11px] text-gray-500">Welcome, {user?.full_name}</p>
            </div>
            {plan_name && (
              <button
                data-testid="header-plan-badge"
                onClick={() => navigate('/billing')}
                title="View / change plan"
                className="hidden md:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-teal-50 border border-teal-200 text-teal-700 text-[11px] font-semibold tracking-wide hover:bg-teal-100 transition"
              >
                <span>{plan_name}</span>
                {billing_status === 'past_due' && (
                  <span className="text-red-600 text-[10px] uppercase font-bold">past due</span>
                )}
                {billing_status === 'cancelled' && (
                  <span className="text-amber-600 text-[10px] uppercase font-bold">cancelled</span>
                )}
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Button variant="ghost" size="icon" onClick={() => setNotifOpen(!notifOpen)} className="relative">
                <Bell className="w-5 h-5 text-gray-600" />
                {unreadCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 text-white text-[9px] font-bold rounded-full flex items-center justify-center">{unreadCount}</span>
                )}
              </Button>
              {notifOpen && (
                <div className="absolute right-0 top-11 w-80 bg-white rounded-xl shadow-lg border border-gray-200 z-50">
                  <div className="p-3 border-b border-gray-100">
                    <h3 className="text-sm font-semibold text-gray-900">Notifications</h3>
                  </div>
                  <div className="max-h-64 overflow-y-auto">
                    {notifications.length === 0 ? (
                      <p className="p-4 text-sm text-gray-500 text-center">No notifications</p>
                    ) : (
                      notifications.slice(0, 5).map(n => (
                        <div key={n.id}
                          className={`p-3 border-b border-gray-50 hover:bg-gray-50 cursor-pointer ${n.status === 'unread' ? 'bg-teal-50/50' : ''}`}
                          onClick={() => { onNotificationRead?.(n.id); if (n.appointment_id) navigate('/appointments'); setNotifOpen(false); }}>
                          <div className="flex items-start gap-2">
                            {n.metadata?.is_emergency && <Badge variant="destructive" className="text-[9px] shrink-0 mt-0.5">URGENT</Badge>}
                            <div className="min-w-0">
                              <p className="text-xs font-medium text-gray-900 truncate">{n.title}</p>
                              <p className="text-[11px] text-gray-500 mt-0.5 line-clamp-2">{n.message}</p>
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
            <div className="w-8 h-8 rounded-full bg-teal-100 flex items-center justify-center">
              <span className="text-xs font-semibold text-teal-700">{user?.full_name?.charAt(0) || 'U'}</span>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
