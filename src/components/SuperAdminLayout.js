import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  LayoutGrid, Building2, Phone, LogOut, ShieldAlert, Menu, ChevronLeft, Cpu,
} from 'lucide-react';

/**
 * Platform Console — dedicated UI for super_admins only.
 * Hard-separated from the practice portal: dark slate theme, no patient
 * data, no appointment data, no practice-level features. This is the
 * SaaS owner's workspace.
 */
export default function SuperAdminLayout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const navItems = [
    { path: '/admin', label: 'Dashboard', icon: LayoutGrid, exact: true },
    { path: '/admin/practices', label: 'Manage Practices', icon: Building2 },
    { path: '/admin/retell', label: 'Retell Provisioning', icon: Phone },
    { path: '/admin/llm', label: 'LLM Routing', icon: Cpu },
  ];

  const isActive = (item) => item.exact
    ? location.pathname === item.path
    : location.pathname.startsWith(item.path);

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <aside
        data-testid="superadmin-sidebar"
        className={`flex flex-col bg-slate-900 border-r border-slate-800 transition-all duration-300 ${
          sidebarOpen ? 'w-64' : 'w-[72px]'
        }`}
      >
        <div className="flex items-center gap-3 px-4 h-16 border-b border-slate-800 shrink-0">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-red-500 to-amber-500 flex items-center justify-center shrink-0 shadow-lg shadow-red-500/20">
            <ShieldAlert className="w-5 h-5 text-white" />
          </div>
          {sidebarOpen && (
            <div className="overflow-hidden">
              <h1 className="text-sm font-bold text-white truncate tracking-tight">Platform Console</h1>
              <p className="text-[10px] text-amber-400 uppercase tracking-widest font-semibold">Super Admin</p>
            </div>
          )}
        </div>

        <nav className="flex-1 py-4 px-2 overflow-y-auto space-y-1">
          {navItems.map(item => {
            const active = isActive(item);
            const Icon = item.icon;
            return (
              <button
                key={item.path}
                data-testid={`nav-${item.path.replace(/\//g, '-')}`}
                onClick={() => navigate(item.path)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all
                  ${active
                    ? 'bg-gradient-to-r from-red-500/15 to-amber-500/10 text-amber-200 border border-amber-500/30 shadow-inner'
                    : 'text-slate-400 hover:bg-slate-800 hover:text-slate-100'}`}
              >
                <Icon className={`w-4 h-4 shrink-0 ${active ? 'text-amber-400' : 'text-slate-500'}`} />
                {sidebarOpen && <span className="truncate">{item.label}</span>}
              </button>
            );
          })}
        </nav>

        <div className="p-3 border-t border-slate-800 space-y-2">
          {sidebarOpen && (
            <div className="px-2 py-2">
              <p className="text-xs font-semibold text-slate-200 truncate">{user?.full_name}</p>
              <p className="text-[10px] text-slate-500 truncate">{user?.email}</p>
              <span className="inline-block mt-1.5 text-[9px] font-bold tracking-wider uppercase px-2 py-0.5 rounded bg-red-500/15 text-red-300 border border-red-500/30">
                Platform Owner
              </span>
            </div>
          )}
          <button
            data-testid="superadmin-signout"
            onClick={() => { logout(); navigate('/login'); }}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium text-slate-400 hover:bg-red-500/10 hover:text-red-300 transition-colors"
          >
            <LogOut className="w-4 h-4 shrink-0" />
            {sidebarOpen && <span>Sign Out</span>}
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="h-16 bg-slate-900/60 backdrop-blur-sm border-b border-slate-800 flex items-center justify-between px-6 shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition"
            >
              {sidebarOpen ? <ChevronLeft className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
            <div>
              <h2 className="text-sm font-semibold text-slate-100">DentalAI · Platform Operations</h2>
              <p className="text-[11px] text-slate-500">Infrastructure-level controls. Not visible to clinics.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[11px] font-semibold tracking-wider uppercase">
              <ShieldAlert className="w-3 h-3" /> Super Admin Mode
            </span>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto bg-slate-950">
          {children}
        </main>
      </div>
    </div>
  );
}
