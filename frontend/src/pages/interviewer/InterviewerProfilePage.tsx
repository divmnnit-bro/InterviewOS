import React from 'react';
import { Award, Mail, Info } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, Badge } from '@/components/ui';

export const InterviewerProfilePage: React.FC = () => {
  const { user } = useAuth();

  const skills = user?.skills || user?.interviewer?.skills || [];
  const capacity = user?.capacity || user?.interviewer?.capacity || 4;
  const department = user?.department || user?.interviewer?.department || 'Not specified';

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-100 tracking-tight flex items-center gap-2.5">
          <Award className="w-6 h-6 text-brand-400" />
          <span>Interviewer Profile</span>
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Your verified interviewer attributes used by the CP-SAT scheduler
        </p>
      </div>

      <div className="p-4 rounded-xl bg-surface-elevated/70 border border-surface-border flex items-start gap-3 text-xs text-slate-300">
        <Info className="w-5 h-5 text-brand-400 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold text-slate-100 mb-0.5">Profile Management Policy:</p>
          <p>
            Your panel skills, departmental affiliation, and maximum daily interview capacity are configured and managed directly by recruitment coordinators. The backend provides read-only inspection for interviewers to maintain audit compliance. If adjustments are needed, please contact your placement coordinator.
          </p>
        </div>
      </div>

      <Card className="space-y-6">
        <CardHeader>
          <div>
            <CardTitle>Account Details</CardTitle>
            <CardDescription>Primary identity</CardDescription>
          </div>
          <Badge variant="success">Active Interviewer</Badge>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-surface-elevated/50 border border-surface-border">
              <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold block mb-1">
                Full Name
              </span>
              <span className="text-sm font-bold text-slate-100">{user?.name}</span>
            </div>

            <div className="p-4 rounded-xl bg-surface-elevated/50 border border-surface-border">
              <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold block mb-1">
                Institutional Email
              </span>
              <span className="text-sm font-mono text-slate-100 flex items-center gap-1.5">
                <Mail className="w-4 h-4 text-slate-500" />
                <span>{user?.email}</span>
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-surface-elevated/50 border border-surface-border">
              <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold block mb-1">
                Department
              </span>
              <span className="text-sm font-semibold text-slate-100">{department}</span>
            </div>

            <div className="p-4 rounded-xl bg-surface-elevated/50 border border-surface-border">
              <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold block mb-1">
                Max Daily Capacity
              </span>
              <span className="text-sm font-bold text-emerald-400">{capacity} interviews / day</span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-surface-elevated/50 border border-surface-border">
            <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold block mb-2">
              Tagged Technical Skills &amp; Domains
            </span>
            {skills.length === 0 ? (
              <p className="text-xs text-slate-500">No skill tags assigned yet.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {skills.map((s) => (
                  <Badge key={s} variant="brand" size="md">
                    {s}
                  </Badge>
                ))}
              </div>
            )}
            <p className="text-[11px] text-slate-500 mt-2">
              The automated scheduler matches you only with candidate stages requiring these tags.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
