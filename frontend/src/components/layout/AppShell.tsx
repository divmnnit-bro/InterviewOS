import React, { useState, useRef, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Calendar,
  Users,
  Building,
  CheckCircle,
  Menu,
  X,
  LogOut,
  Clock,
  Sparkles,
  ChevronDown,
  Layers,
  LayoutDashboard,
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { NotificationBell } from './NotificationBell';
import { animateDrawerIn } from '@/lib/animations';

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
}

export const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, role, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (mobileDrawerOpen && drawerRef.current) {
      animateDrawerIn(drawerRef.current);
    }
  }, [mobileDrawerOpen]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Close drawer on route change
  useEffect(() => {
    setMobileDrawerOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getNavItems = (): NavItem[] => {
    if (role === 'coordinator') {
      return [
        { label: 'Overview', href: '/coordinator', icon: <LayoutDashboard className="w-4 h-4" /> },
        { label: 'Drives', href: '/coordinator/drives', icon: <Layers className="w-4 h-4" /> },
        { label: 'People', href: '/coordinator/people', icon: <Users className="w-4 h-4" /> },
        { label: 'Rooms', href: '/coordinator/rooms', icon: <Building className="w-4 h-4" /> },
      ];
    }
    if (role === 'interviewer') {
      return [
        { label: 'Dashboard', href: '/interviewer', icon: <LayoutDashboard className="w-4 h-4" /> },
        { label: 'My Interviews', href: '/interviewer/interviews', icon: <Calendar className="w-4 h-4" /> },
        { label: 'My Availability', href: '/interviewer/availability', icon: <Clock className="w-4 h-4" /> },
        { label: 'My Profile', href: '/interviewer/profile', icon: <Users className="w-4 h-4" /> },
      ];
    }
    if (role === 'candidate') {
      return [
        { label: 'Dashboard', href: '/candidate', icon: <LayoutDashboard className="w-4 h-4" /> },
        { label: 'My Progress', href: '/candidate/interviews', icon: <CheckCircle className="w-4 h-4" /> },
        { label: 'My Availability', href: '/candidate/availability', icon: <Clock className="w-4 h-4" /> },
      ];
    }
    return [];
  };

  const navItems = getNavItems();

  const roleBadgeColors: Record<string, string> = {
    coordinator: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
    interviewer: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    candidate: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
  };

  return (
    <div className="min-h-screen flex bg-background text-slate-100">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex lg:flex-col w-64 bg-surface-card border-r border-surface-border shrink-0 select-none">
        {/* Brand */}
        <div className="h-16 flex items-center px-6 border-b border-surface-border/60">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-brand-600 to-indigo-500 flex items-center justify-center text-white shadow-md shadow-brand-500/30 group-hover:scale-105 transition-transform">
              <Sparkles className="w-4 h-4" />
            </div>
            <div className="flex flex-col">
              <span className="font-bold text-base tracking-tight text-slate-100 group-hover:text-brand-300 transition-colors">
                InterviewOS
              </span>
              <span className="text-[10px] text-slate-500 font-medium tracking-wider uppercase">
                Autonomous Ops
              </span>
            </div>
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const isActive =
              location.pathname === item.href ||
              (item.href !== `/${role}` && location.pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                to={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-brand-600 text-white shadow-sm shadow-brand-900/40'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-surface-elevated/70'
                }`}
              >
                {item.icon}
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* User Card in Sidebar Bottom */}
        <div className="p-3 border-t border-surface-border/60">
          <div className="p-3 rounded-xl bg-surface-elevated/60 border border-surface-border/60 flex items-center justify-between">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-8 h-8 rounded-full bg-brand-600/20 text-brand-400 font-bold flex items-center justify-center text-xs border border-brand-500/30 shrink-0">
                {user?.name ? user.name.slice(0, 2).toUpperCase() : 'U'}
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-slate-200 truncate">{user?.name}</p>
                <span
                  className={`inline-block text-[10px] uppercase font-semibold px-1.5 py-0.2 rounded-full border ${
                    role ? roleBadgeColors[role] : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  {role}
                </span>
              </div>
            </div>
            <button
              onClick={handleLogout}
              title="Sign out"
              className="text-slate-400 hover:text-rose-400 p-1.5 rounded-lg hover:bg-surface-hover transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header */}
        <header className="h-16 bg-surface-card/80 backdrop-blur-md border-b border-surface-border flex items-center justify-between px-4 sm:px-8 sticky top-0 z-30">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileDrawerOpen(true)}
              className="lg:hidden p-2 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-surface-elevated"
              aria-label="Open navigation menu"
            >
              <Menu className="w-5 h-5" />
            </button>

            {/* Breadcrumb or View indicator */}
            <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
              <span className="uppercase tracking-wider text-slate-500 font-semibold">{role}</span>
              <span>/</span>
              <span className="text-slate-200 capitalize">
                {location.pathname.split('/')[2] || 'Home'}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <NotificationBell />

            {/* User Menu on Header */}
            <div className="relative" ref={userMenuRef}>
              <button
                onClick={() => setUserMenuOpen(!userMenuOpen)}
                className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-surface-elevated transition-colors text-left"
              >
                <div className="w-7 h-7 rounded-full bg-brand-600/30 text-brand-300 font-semibold flex items-center justify-center text-xs border border-brand-500/30">
                  {user?.name ? user.name.slice(0, 1).toUpperCase() : 'U'}
                </div>
                <span className="hidden md:inline text-xs font-medium text-slate-200">
                  {user?.name}
                </span>
                <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
              </button>

              {userMenuOpen && (
                <div className="absolute right-0 mt-2 w-52 rounded-xl bg-surface-card border border-surface-border shadow-2xl z-50 py-1 overflow-hidden">
                  <div className="px-3.5 py-2.5 border-b border-surface-border/60">
                    <p className="text-xs font-semibold text-slate-200 truncate">{user?.name}</p>
                    <p className="text-[11px] text-slate-400 truncate">{user?.email}</p>
                  </div>
                  <Link
                    to="/notifications"
                    onClick={() => setUserMenuOpen(false)}
                    className="flex items-center gap-2 px-3.5 py-2 text-xs text-slate-300 hover:text-slate-100 hover:bg-surface-elevated"
                  >
                    <span>Inbox &amp; Alerts</span>
                  </Link>
                  <button
                    onClick={handleLogout}
                    className="w-full flex items-center gap-2 px-3.5 py-2 text-xs text-rose-400 hover:bg-rose-500/10 transition-colors text-left"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span>Sign Out</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Mobile Drawer */}
        {mobileDrawerOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <div
              className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm"
              onClick={() => setMobileDrawerOpen(false)}
            />
            <div
              ref={drawerRef}
              className="relative w-72 max-w-[80vw] h-full bg-surface-card border-r border-surface-border flex flex-col p-4 shadow-2xl"
            >
              <div className="flex items-center justify-between pb-4 border-b border-surface-border/60">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center text-white">
                    <Sparkles className="w-3.5 h-3.5" />
                  </div>
                  <span className="font-bold text-sm text-slate-100">InterviewOS</span>
                </div>
                <button
                  onClick={() => setMobileDrawerOpen(false)}
                  className="p-1 rounded-lg text-slate-400 hover:text-slate-100"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <nav className="flex-1 py-4 space-y-1">
                {navItems.map((item) => (
                  <Link
                    key={item.href}
                    to={item.href}
                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-slate-300 hover:text-slate-100 hover:bg-surface-elevated"
                  >
                    {item.icon}
                    <span>{item.label}</span>
                  </Link>
                ))}
              </nav>

              <div className="pt-4 border-t border-surface-border/60">
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 text-sm font-medium transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign Out</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Main Content Body */}
        <main className="flex-1 p-4 sm:p-8 max-w-7xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
};
