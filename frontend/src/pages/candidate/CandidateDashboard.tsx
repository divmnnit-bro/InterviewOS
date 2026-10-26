import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Clock,
  CheckCircle,
  Bell,
  Calendar,
  Building,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Users,
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { apiClient } from '@/api/client';
import { Notification } from '@/types/api';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Button,
  Badge,
  Spinner,
} from '@/components/ui';
import { formatTimeUTC } from '@/lib/timelineMath';
import { CalendarDownloadButton } from '@/components/schedule/CalendarDownloadButton';

export interface MyInterview {
  id: string;
  drive_id: string;
  drive_title: string;
  stage_id: string;
  stage_name: string;
  room_id?: string;
  room_name?: string;
  start_time: string;
  end_time: string;
  status: string;
  version: number;
  panel_names: string[];
  evaluation_submitted?: boolean | null;
}

export interface DecidedRoundResult {
  stage_id: string;
  stage_name: string;
  order_index: number;
  result?: 'advanced' | 'selected' | 'not_selected' | null;
}

export interface CandidateDriveProgress {
  drive_id: string;
  drive_title: string;
  enrolment_status: string;
  current_stage_id?: string;
  current_stage_name?: string;
  rounds: DecidedRoundResult[];
}

export const CandidateDashboard: React.FC<{ focusProgress?: boolean }> = ({ focusProgress = false }) => {
  const { user } = useAuth();

  // Queries
  const { data: myInterviews = [], isLoading: isInterviewsLoading } = useQuery<MyInterview[]>({
    queryKey: ['my-interviews'],
    queryFn: () => apiClient<MyInterview[]>('/me/interviews'),
  });

  const { data: progressList = [], isLoading: isProgressLoading } = useQuery<CandidateDriveProgress[]>({
    queryKey: ['my-progress'],
    queryFn: () => apiClient<CandidateDriveProgress[]>('/me/progress'),
  });

  const { data: notifications = [] } = useQuery<Notification[]>({
    queryKey: ['notifications'],
    queryFn: () => apiClient<Notification[]>('/notifications?unread_only=false&limit=5'),
  });

  useEffect(() => {
    if (!focusProgress) return;
    requestAnimationFrame(() => document.getElementById('candidate-progress')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  }, [focusProgress]);

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-indigo-950/60 via-slate-900 to-slate-900 border border-indigo-500/20 shadow-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <span className="text-xs uppercase font-semibold text-indigo-400 tracking-wider">Candidate Portal</span>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight mt-1">Welcome, {user?.name}</h1>
          <p className="text-xs text-slate-400 mt-1 max-w-xl">
            Keep your availability updated, track your recruitment drive progress across rounds, and access scheduled interview sessions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link to="/candidate/availability">
            <Button variant="primary" size="sm" leftIcon={<Clock className="w-4 h-4" />}>
              Set Availability
            </Button>
          </Link>
        </div>
      </div>

      {/* Grid: Interviews & Progress */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Card 1: My Scheduled Interviews */}
        <Card className="flex flex-col justify-between">
          <div>
            <CardHeader>
              <div>
                <CardTitle>My Interviews</CardTitle>
                <CardDescription>Upcoming and confirmed interview sessions</CardDescription>
              </div>
              <Calendar className="w-5 h-5 text-indigo-400" />
            </CardHeader>
            <CardContent>
              {isInterviewsLoading ? (
                <div className="py-8 text-center">
                  <Spinner size="md" className="mx-auto" />
                </div>
              ) : myInterviews.length === 0 ? (
                <div className="text-center py-8">
                  <Calendar className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                  <p className="text-xs text-slate-400">No interviews currently scheduled.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {myInterviews.map((iv) => {
                    const dateFormatted = new Date(iv.start_time).toLocaleDateString([], {
                      weekday: 'short',
                      month: 'short',
                      day: 'numeric',
                    });
                    const startFormatted = formatTimeUTC(iv.start_time);
                    const endFormatted = formatTimeUTC(iv.end_time);

                    return (
                      <div
                        key={iv.id}
                        className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80 space-y-2"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <span className="text-[10px] font-semibold text-indigo-400 uppercase tracking-wider">
                              {iv.drive_title}
                            </span>
                            <h4 className="text-sm font-bold text-slate-200">{iv.stage_name}</h4>
                          </div>
                          <Badge
                            variant={
                              iv.status === 'confirmed' || iv.status === 'scheduled'
                                ? 'success'
                                : 'brand'
                            }
                            size="sm"
                          >
                            {iv.status}
                          </Badge>
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-xs text-slate-400 pt-1 border-t border-slate-800/40 font-mono">
                          <div className="flex items-center gap-1.5">
                            <Clock className="w-3.5 h-3.5 text-slate-500" />
                            <span>
                              {dateFormatted} {startFormatted} - {endFormatted}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <Building className="w-3.5 h-3.5 text-slate-500" />
                            <span className="truncate">{iv.room_name || 'Room Assigned'}</span>
                          </div>
                        </div>

                        {iv.panel_names.length > 0 && (
                          <div className="text-[11px] text-slate-400 flex items-center gap-1.5">
                            <Users className="w-3.5 h-3.5 text-slate-500" />
                            <span>Panel: {iv.panel_names.join(', ')}</span>
                          </div>
                        )}

                        <div className="pt-2 flex justify-end">
                          <CalendarDownloadButton
                            interviewId={iv.id}
                            label="Add to Calendar (.ics)"
                            variant="outline"
                            className="border-indigo-500/20 bg-indigo-600/20 text-indigo-300 hover:bg-indigo-600/30"
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </div>
        </Card>

        {/* Card 2: Drive Progress & Round Decisions */}
        <Card id="candidate-progress" className="flex flex-col justify-between scroll-mt-6">
          <div>
            <CardHeader>
              <div>
                <CardTitle>My Progress</CardTitle>
                <CardDescription>Stage progression &amp; decided results per round</CardDescription>
              </div>
              <CheckCircle className="w-5 h-5 text-emerald-400" />
            </CardHeader>
            <CardContent>
              {isProgressLoading ? (
                <div className="py-8 text-center">
                  <Spinner size="md" className="mx-auto" />
                </div>
              ) : progressList.length === 0 ? (
                <div className="text-center py-8">
                  <CheckCircle2 className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                  <p className="text-xs text-slate-400">No active drive enrollments found.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {progressList.map((prog) => (
                    <div
                      key={prog.drive_id}
                      className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="text-sm font-bold text-slate-200">{prog.drive_title}</h4>
                          <p className="text-xs text-slate-400 mt-0.5">
                            Current Stage:{' '}
                            <span className="text-indigo-300 font-medium">
                              {prog.current_stage_name || 'Enrolled'}
                            </span>
                          </p>
                        </div>
                        <Badge
                          variant={
                            prog.enrolment_status === 'selected'
                              ? 'success'
                              : prog.enrolment_status === 'rejected'
                              ? 'danger'
                              : 'brand'
                          }
                        >
                          {prog.enrolment_status}
                        </Badge>
                      </div>

                      {/* Rounds Progress List */}
                      <div className="space-y-2 pt-1 border-t border-slate-800/60">
                        {prog.rounds.map((round) => (
                          <div
                            key={round.stage_id}
                            className="flex items-center justify-between text-xs p-2 rounded-lg bg-slate-900 border border-slate-800/60"
                          >
                            <span className="font-medium text-slate-300">
                              {round.order_index + 1}. {round.stage_name}
                            </span>
                            {round.result === 'advanced' ? (
                              <Badge variant="success" size="sm" className="flex items-center gap-1">
                                <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                                Advanced
                              </Badge>
                            ) : round.result === 'selected' ? (
                              <Badge variant="success" size="sm" className="flex items-center gap-1">
                                <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                                Selected
                              </Badge>
                            ) : round.result === 'not_selected' ? (
                              <Badge variant="danger" size="sm" className="flex items-center gap-1">
                                <XCircle className="w-3 h-3 text-rose-400" />
                                Not Selected
                              </Badge>
                            ) : (
                              <Badge variant="neutral" size="sm" className="flex items-center gap-1">
                                <HelpCircle className="w-3 h-3 text-slate-500" />
                                In Progress
                              </Badge>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </div>
        </Card>
      </div>

      {/* Notifications Card */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Recent Notifications</CardTitle>
            <CardDescription>Updates from your coordinators and interviewers</CardDescription>
          </div>
          <Bell className="w-5 h-5 text-indigo-400" />
        </CardHeader>
        <CardContent>
          {notifications.length === 0 ? (
            <p className="text-xs text-slate-400 py-3 text-center">No notifications yet.</p>
          ) : (
            <div className="divide-y divide-slate-800/60">
              {notifications.map((n) => (
                <div key={n.id} className="py-3 flex items-start justify-between gap-4">
                  <div>
                    <h5 className="text-xs font-semibold text-slate-200">{n.title}</h5>
                    <p className="text-xs text-slate-400 mt-0.5">{n.message}</p>
                  </div>
                  <span className="text-[10px] text-slate-500 shrink-0 font-mono">
                    {new Date(n.created_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
