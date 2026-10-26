import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldAlert, ArrowLeft } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui';

export const NotAllowedPage: React.FC = () => {
  const { role, logout } = useAuth();

  const homePath = role ? `/${role}` : '/login';

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-6">
      <div className="max-w-md w-full text-center bg-surface-card border border-surface-border p-8 rounded-2xl shadow-2xl">
        <div className="w-16 h-16 rounded-2xl bg-rose-500/10 text-rose-400 flex items-center justify-center mx-auto mb-4 border border-rose-500/20">
          <ShieldAlert className="w-8 h-8" />
        </div>
        <h1 className="text-xl font-bold text-slate-100 mb-2">Access Restricted</h1>
        <p className="text-sm text-slate-400 mb-6 leading-relaxed">
          Your current account role (<span className="text-brand-300 font-semibold">{role || 'unauthenticated'}</span>) does not have authorization to view this area.
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-3">
          <Link to={homePath} className="w-full">
            <Button variant="primary" className="w-full" leftIcon={<ArrowLeft className="w-4 h-4" />}>
              Return to My Area
            </Button>
          </Link>
          <Button variant="outline" className="w-full" onClick={logout}>
            Sign Out
          </Button>
        </div>
      </div>
    </div>
  );
};

export const NotFoundPage: React.FC = () => {
  const { role } = useAuth();
  const homePath = role ? `/${role}` : '/login';

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-6">
      <div className="max-w-md w-full text-center bg-surface-card border border-surface-border p-8 rounded-2xl shadow-2xl">
        <div className="text-5xl font-black text-brand-500 mb-2 font-mono">404</div>
        <h1 className="text-xl font-bold text-slate-100 mb-2">Page Not Found</h1>
        <p className="text-sm text-slate-400 mb-6">
          The requested page or resource could not be found.
        </p>
        <Link to={homePath}>
          <Button variant="primary" leftIcon={<ArrowLeft className="w-4 h-4" />}>
            Back to Safety
          </Button>
        </Link>
      </div>
    </div>
  );
};
