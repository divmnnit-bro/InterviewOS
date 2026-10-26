import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Clock,
  Calendar,
  Bell,
  ArrowRight,
  Award,
  AlertCircle,
  Building,
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
import { formatTimeUTC, getDateString } from '@/lib/timelineMath';
import { EvaluationModal } from '@/components/interviewer/EvaluationModal';
import { MyInterview } from './InterviewerInterviewsPage';

export const InterviewerDashboard: React.FC = () => {
  const { user } = useAuth();
  const [evalModalInterview, setEvalModalInterview] = useState<MyInterview | null>(null);

  const { data: interviews = [], isLoading: isInterviewsLoading, refetch } = useQuery<MyInterview[]>({
    queryKey: ['my-interviews'],
    queryFn: () => apiClient<MyInterview[]>('/me/interviews'),
  });

  const { data: notifications = [] } = useQuery<Notification[]>({
    queryKey: ['notifications'],
    queryFn: () => apiClient<Notification[]>('/notifications?unread_only=false&limit=5'),
  });

  const now = new Date();
  const todayStr = getDateString(now.toISOString());

  const todayInterviews = interviews.filter(
    (iv) => getDateString(iv.start_time) === todayStr
  );

  const needsEvaluation = interviews.filter((iv) => {
    const start = new Date(iv.start_time);
    return now >= start && ['scheduled', 'confirmed', 'completed'].includes(iv.status) && !iv.evaluation_submitted;
  });

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-indigo-950/60 via-slate-900 to-slate-900 border border-indigo-500/20 shadow-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <span className="text-xs uppercase font-semibold text-indigo-400 tracking-wider">Interviewer Console</span>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight mt-1">Hello, {user?.name}</h1>
          <p className="text-xs text-slate-400 mt-1 max-w-xl">
            Review your assigned interview sessions, submit candidate evaluations, and manage your weekly availability load.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Link to="/interviewer/availability">
            <Button variant="primary" size="sm" leftIcon={<Clock className="w-4 h-4" />}>
              My Availability
            </Button>
          </Link>
          <Link to="/interviewer/interviews">
            <Button variant="secondary" size="sm" leftIcon={<Calendar className="w-4 h-4" />}>
              All Interviews ({interviews.length})
            </Button>
          </Link>
        </div>
      </div>

      {/* Action Section: Pending Feedback Banner */}
      {needsEvaluation.length > 0 && (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-amber-400 shrink-0" />
            <div>
              <h4 className="text-sm font-bold text-amber-300">
                {needsEvaluation.length} Interview{needsEvaluation.length > 1 ? 's' : ''} Awaiting Your Evaluation
              </h4>
              <p className="text-xs text-amber-200/80 mt-0.5">
                Submit rubric ratings and recommendations to advance candidates to the next round.
              </p>
            </div>
          </div>
          <Link to="/interviewer/interviews">
            <Button
              variant="outline"
              size="sm"
              className="border-amber-500/30 text-amber-300 hover:bg-amber-500/20 whitespace-nowrap"
            >
              Review Now
              <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
            </Button>
          </Link>
        </div>
      )}

      {/* Grid: Today's Schedule & Workload */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Today's Interviews Card */}
        <Card className="flex flex-col justify-between">
          <div>
            <CardHeader>
              <div>
                <CardTitle>Today's Interviews</CardTitle>
                <CardDescription>Scheduled sessions for {new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}</CardDescription>
              </div>
              <Calendar className="w-5 h-5 text-indigo-400" />
            </CardHeader>
            <CardContent>
              {isInterviewsLoading ? (
                <div className="py-8 text-center">
                  <Spinner size="md" className="mx-auto" />
                </div>
              ) : todayInterviews.length === 0 ? (
                <div className="text-center py-8">
                  <Calendar className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                  <p className="text-xs text-slate-400">No interviews scheduled for today.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {todayInterviews.map((iv) => (
                    <div
                      key={iv.id}
                      className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between gap-3"
                    >
                      <div>
                        <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">
                          {iv.drive_title}
                        </span>
                        <h4 className="text-sm font-bold text-slate-200">
                          {iv.candidate_name || 'Candidate'}
                        </h4>
                        <div className="flex items-center gap-3 text-xs text-slate-400 font-mono mt-1">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3 text-slate-500" />
                            {formatTimeUTC(iv.start_time)} - {formatTimeUTC(iv.end_time)}
                          </span>
                          <span className="flex items-center gap-1">
                            <Building className="w-3 h-3 text-slate-500" />
                            {iv.room_name || 'Room Assigned'}
                          </span>
                        </div>
                      </div>

                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => setEvalModalInterview(iv)}
                        className="bg-indigo-600 hover:bg-indigo-500 text-xs shrink-0"
                      >
                        <Award className="w-3.5 h-3.5 mr-1" />
                        Evaluate
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </div>
          <div className="p-4 border-t border-slate-800">
            <Link to="/interviewer/interviews" className="w-full">
              <Button variant="ghost" size="sm" className="w-full justify-between text-slate-400 hover:text-slate-200">
                <span>View Full Interview Schedule</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Button>
            </Link>
          </div>
        </Card>

        {/* Profile, Capacity & Notifications */}
        <div className="space-y-6">
          {/* Availability & Capacity Card */}
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Daily Load &amp; Capacity</CardTitle>
                <CardDescription>Solver limits for your schedule</CardDescription>
              </div>
              <Clock className="w-5 h-5 text-emerald-400" />
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between text-xs">
                <span className="text-slate-400">Daily Interview Capacity:</span>
                <span className="font-mono font-bold text-slate-100">
                  {user?.capacity || user?.interviewer?.capacity || 4} slots / day
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                <span className="text-xs text-slate-400 mr-2">Skills:</span>
                {(user?.skills || user?.interviewer?.skills || []).length === 0 ? (
                  <span className="text-xs text-slate-500">None assigned</span>
                ) : (
                  (user?.skills || user?.interviewer?.skills || []).map((skill) => (
                    <Badge key={skill} variant="brand" size="sm">
                      {skill}
                    </Badge>
                  ))
                )}
              </div>
            </CardContent>
            <div className="p-4 border-t border-slate-800">
              <Link to="/interviewer/availability">
                <Button variant="outline" size="sm" className="w-full border-slate-700 text-slate-300">
                  Update Availability Windows
                </Button>
              </Link>
            </div>
          </Card>

          {/* Notifications Card */}
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Notifications</CardTitle>
                <CardDescription>Recent updates and schedule invitations</CardDescription>
              </div>
              <Bell className="w-5 h-5 text-indigo-400" />
            </CardHeader>
            <CardContent>
              {notifications.length === 0 ? (
                <p className="text-xs text-slate-500 py-2 text-center">No new notifications</p>
              ) : (
                <div className="space-y-2.5">
                  {notifications.slice(0, 3).map((n) => (
                    <div key={n.id} className="text-xs">
                      <p className="font-semibold text-slate-200">{n.title}</p>
                      <p className="text-slate-400 mt-0.5">{n.message}</p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Evaluation Modal */}
      {evalModalInterview && (
        <EvaluationModal
          isOpen={!!evalModalInterview}
          onClose={() => setEvalModalInterview(null)}
          interviewId={evalModalInterview.id}
          candidateName={evalModalInterview.candidate_name || 'Candidate'}
          stageName={evalModalInterview.stage_name}
          driveTitle={evalModalInterview.drive_title}
          startTime={evalModalInterview.start_time}
          endTime={evalModalInterview.end_time}
          onSubmitted={() => refetch()}
        />
      )}
    </div>
  );
};
