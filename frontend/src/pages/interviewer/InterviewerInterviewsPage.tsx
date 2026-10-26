import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Calendar,
  Clock,
  Building,
  Award,
} from 'lucide-react';
import { apiClient } from '@/api/client';
import { Card, Button, Badge, Spinner } from '@/components/ui';
import { formatTimeUTC, groupByDay } from '@/lib/timelineMath';
import { EvaluationModal } from '@/components/interviewer/EvaluationModal';
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
  candidate_name?: string;
  evaluation_submitted?: boolean;
}

export const InterviewerInterviewsPage: React.FC = () => {
  const [filter, setFilter] = useState<'all' | 'upcoming' | 'needs_feedback' | 'completed'>('all');
  const [selectedInterviewForEval, setSelectedInterviewForEval] = useState<MyInterview | null>(null);

  const { data: interviews = [], isLoading, refetch } = useQuery<MyInterview[]>({
    queryKey: ['my-interviews'],
    queryFn: () => apiClient<MyInterview[]>('/me/interviews'),
  });

  const now = new Date();

  const filteredInterviews = interviews.filter((iv) => {
    const start = new Date(iv.start_time);
    const end = new Date(iv.end_time);

    if (filter === 'upcoming') {
      return start > now;
    }
    if (filter === 'needs_feedback') {
      return now >= start && ['scheduled', 'confirmed', 'completed'].includes(iv.status) && !iv.evaluation_submitted;
    }
    if (filter === 'completed') {
      return iv.status === 'completed' || now > end;
    }
    return true;
  });

  // Group by day for agenda view
  const dayGroups = groupByDay(
    filteredInterviews.map((i) => ({ ...i, startTime: i.start_time }))
  );

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight">My Interview Panels</h1>
          <p className="text-xs text-slate-400 mt-1">
            Review your assigned interview sessions, export calendar files, and submit rubric evaluations.
          </p>
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 p-1 bg-slate-900 border border-slate-800 rounded-xl">
          <button
            onClick={() => setFilter('all')}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
              filter === 'all'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All ({interviews.length})
          </button>
          <button
            onClick={() => setFilter('upcoming')}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
              filter === 'upcoming'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Upcoming
          </button>
          <button
            onClick={() => setFilter('needs_feedback')}
            className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
              filter === 'needs_feedback'
                ? 'bg-amber-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Needs Feedback
          </button>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <Card className="p-12 text-center bg-slate-900/60 border-slate-800">
          <Spinner size="lg" className="mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Loading your interviews...</p>
        </Card>
      ) : filteredInterviews.length === 0 ? (
        <Card className="p-12 text-center bg-slate-900/60 border-slate-800">
          <Calendar className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <h3 className="text-base font-semibold text-slate-200">No Interviews Found</h3>
          <p className="text-xs text-slate-400 mt-1">
            {filter === 'upcoming'
              ? 'You have no upcoming interviews scheduled right now.'
              : filter === 'needs_feedback'
              ? 'No interviews currently pending your evaluation.'
              : 'You have not been assigned to any interviews yet.'}
          </p>
        </Card>
      ) : (
        <div className="space-y-6">
          {dayGroups.map((group) => (
            <div key={group.dateStr} className="space-y-3">
              <div className="flex items-center gap-2 px-1">
                <Calendar className="w-4 h-4 text-indigo-400" />
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  {group.label}
                </h3>
                <span className="text-[11px] text-slate-500 font-mono">
                  ({group.items.length} session{group.items.length > 1 ? 's' : ''})
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {group.items.map((iv) => {
                  const startTime = formatTimeUTC(iv.start_time);
                  const endTime = formatTimeUTC(iv.end_time);
                  const hasStarted = now >= new Date(iv.start_time);

                  return (
                    <Card
                      key={iv.id}
                      className="p-5 bg-slate-900/90 border-slate-800 hover:border-slate-700 transition-all flex flex-col justify-between"
                    >
                      <div className="space-y-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider">
                              {iv.drive_title}
                            </span>
                            <h4 className="text-base font-bold text-slate-100 mt-0.5">
                              {iv.candidate_name || 'Candidate'}
                            </h4>
                            <p className="text-xs text-slate-400">Round: {iv.stage_name}</p>
                          </div>
                          <Badge
                            variant={
                              iv.status === 'scheduled' || iv.status === 'confirmed'
                                ? 'success'
                                : 'brand'
                            }
                            size="sm"
                          >
                            {iv.status}
                          </Badge>
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-xs text-slate-400 font-mono pt-2 border-t border-slate-800/80">
                          <div className="flex items-center gap-1.5">
                            <Clock className="w-3.5 h-3.5 text-slate-500" />
                            <span>
                              {startTime} - {endTime}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <Building className="w-3.5 h-3.5 text-slate-500" />
                            <span className="truncate">{iv.room_name || 'Room Assigned'}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center justify-between gap-2 pt-4 mt-3 border-t border-slate-800/60">
                        <CalendarDownloadButton interviewId={iv.id} label=".ics" />

                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => setSelectedInterviewForEval(iv)}
                          className={
                            hasStarted
                              ? 'bg-indigo-600 hover:bg-indigo-500'
                              : 'bg-slate-800 hover:bg-slate-700 text-slate-300'
                          }
                        >
                          <Award className="w-3.5 h-3.5 mr-1.5" />
                          {hasStarted ? 'Evaluate' : 'Preview Rubric'}
                        </Button>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Evaluation Modal */}
      {selectedInterviewForEval && (
        <EvaluationModal
          isOpen={!!selectedInterviewForEval}
          onClose={() => setSelectedInterviewForEval(null)}
          interviewId={selectedInterviewForEval.id}
          candidateName={selectedInterviewForEval.candidate_name || 'Candidate'}
          stageName={selectedInterviewForEval.stage_name}
          driveTitle={selectedInterviewForEval.drive_title}
          startTime={selectedInterviewForEval.start_time}
          endTime={selectedInterviewForEval.end_time}
          onSubmitted={() => {
            refetch();
          }}
        />
      )}
    </div>
  );
};
