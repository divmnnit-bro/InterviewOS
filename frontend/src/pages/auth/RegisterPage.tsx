import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Sparkles, Mail, Lock, User as UserIcon, BookOpen, Hash, ArrowRight, CheckCircle2 } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { Button, Input, FormField, Card } from '@/components/ui';
import { ApiError } from '@/api/client';

export const RegisterPage: React.FC = () => {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rollNumber, setRollNumber] = useState('');
  const [branch, setBranch] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!name || !email || !password) {
      setErrorMessage('Please fill in all required fields.');
      return;
    }

    setIsLoading(true);
    try {
      await register({
        name,
        email,
        password,
        roll_number: rollNumber || undefined,
        branch: branch || undefined,
      });
      setIsSuccess(true);
      setTimeout(() => {
        navigate('/login', { replace: true });
      }, 2000);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message || 'Registration failed.');
      } else {
        setErrorMessage('Failed to register. Please check your details.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4 py-12 relative overflow-hidden">
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-brand-600/10 rounded-full blur-[120px] pointer-events-none" />

      <div className="w-full max-w-md relative z-10">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-gradient-to-tr from-brand-600 to-indigo-500 text-white shadow-xl shadow-brand-500/25 mb-3">
            <Sparkles className="w-6 h-6" />
          </div>
          <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">InterviewOS</h1>
          <p className="text-xs text-slate-400 mt-1">Autonomous campus recruitment &amp; scheduling console</p>
        </div>

        <Card variant="glass" className="p-8 border-surface-border/80">
          <div className="mb-6">
            <h2 className="text-lg font-bold text-slate-100">Candidate Registration</h2>
            <p className="text-xs text-slate-400 mt-0.5">Sign up to self-schedule interviews &amp; track progress</p>
          </div>

          {isSuccess ? (
            <div className="p-6 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-center animate-fadeIn">
              <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-2" />
              <h3 className="text-sm font-bold text-slate-100">Account Created!</h3>
              <p className="text-xs text-slate-300 mt-1">
                Your candidate profile has been registered. Redirecting to sign in...
              </p>
            </div>
          ) : (
            <>
              {errorMessage && (
                <div className="mb-5 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-medium">
                  {errorMessage}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <FormField label="Full Name" required>
                  <Input
                    type="text"
                    placeholder="Jane Doe"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    leftIcon={<UserIcon className="w-4 h-4" />}
                    required
                  />
                </FormField>

                <FormField label="Email address" required>
                  <Input
                    type="email"
                    placeholder="jane@university.edu"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    leftIcon={<Mail className="w-4 h-4" />}
                    autoComplete="email"
                    required
                  />
                </FormField>

                <FormField label="Password" required hint="At least 8 characters recommended">
                  <Input
                    type="password"
                    placeholder="••••••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    leftIcon={<Lock className="w-4 h-4" />}
                    autoComplete="new-password"
                    required
                  />
                </FormField>

                <div className="grid grid-cols-2 gap-3">
                  <FormField label="Roll Number">
                    <Input
                      type="text"
                      placeholder="CS-2026-042"
                      value={rollNumber}
                      onChange={(e) => setRollNumber(e.target.value)}
                      leftIcon={<Hash className="w-3.5 h-3.5" />}
                    />
                  </FormField>

                  <FormField label="Branch / Dept">
                    <Input
                      type="text"
                      placeholder="Computer Science"
                      value={branch}
                      onChange={(e) => setBranch(e.target.value)}
                      leftIcon={<BookOpen className="w-3.5 h-3.5" />}
                    />
                  </FormField>
                </div>

                <Button
                  type="submit"
                  variant="primary"
                  className="w-full mt-2"
                  isLoading={isLoading}
                  rightIcon={<ArrowRight className="w-4 h-4" />}
                >
                  Create Candidate Account
                </Button>
              </form>

              <div className="mt-6 pt-5 border-t border-surface-border/60 text-center">
                <p className="text-xs text-slate-400">
                  Already have an account?{' '}
                  <Link to="/login" className="text-brand-400 hover:text-brand-300 font-semibold underline underline-offset-2">
                    Sign in here
                  </Link>
                </p>
              </div>
            </>
          )}
        </Card>
      </div>
    </div>
  );
};
