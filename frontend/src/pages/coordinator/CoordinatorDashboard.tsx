import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { Layers, Building, Plus, ArrowRight, Calendar } from 'lucide-react';
import { apiClient } from '@/api/client';
import { RecruitmentDrive, Room } from '@/types/api';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, Button, Badge, Spinner, EmptyState } from '@/components/ui';

export const CoordinatorDashboard: React.FC = () => {
  const navigate = useNavigate();
  const { data: drives = [], isLoading: drivesLoading } = useQuery<RecruitmentDrive[]>({
    queryKey: ['drives'],
    queryFn: () => apiClient<RecruitmentDrive[]>('/drives'),
  });

  const { data: rooms = [], isLoading: roomsLoading } = useQuery<Room[]>({
    queryKey: ['rooms'],
    queryFn: () => apiClient<Room[]>('/rooms'),
  });

  const activeDrives = drives.filter(
    (d) => d.status === 'collecting_availability' || d.status === 'scheduling' || d.status === 'published'
  );
  const activeRooms = rooms.filter((r) => r.is_active);

  const driveStatusVariant = (status: string): 'brand' | 'success' | 'warning' | 'danger' | 'neutral' => {
    switch (status) {
      case 'published':
        return 'success';
      case 'collecting_availability':
      case 'scheduling':
        return 'brand';
      case 'completed':
        return 'neutral';
      case 'cancelled':
        return 'danger';
      default:
        return 'warning';
    }
  };

  return (
    <div className="space-y-8">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight">Coordinator Console</h1>
          <p className="text-xs text-slate-400 mt-1">
            Orchestrate drives, calibrate solver parameters, manage candidate pipelines, and run Ripple Rescue
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link to="/coordinator/drives/new">
            <Button variant="primary" size="sm" leftIcon={<Plus className="w-4 h-4" />}>
              Create Drive
            </Button>
          </Link>
          <Link to="/coordinator/rooms">
            <Button variant="secondary" size="sm" leftIcon={<Building className="w-4 h-4" />}>
              Rooms ({rooms.length})
            </Button>
          </Link>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-brand-500/10 text-brand-400 flex items-center justify-center border border-brand-500/20">
            <Layers className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium uppercase tracking-wider">Total Drives</p>
            <h3 className="text-2xl font-bold text-slate-100">{drivesLoading ? '-' : drives.length}</h3>
            <p className="text-[11px] text-slate-500 mt-0.5">{activeDrives.length} active or scheduling</p>
          </div>
        </Card>

        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20">
            <Building className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium uppercase tracking-wider">Interview Rooms</p>
            <h3 className="text-2xl font-bold text-slate-100">{roomsLoading ? '-' : rooms.length}</h3>
            <p className="text-[11px] text-emerald-400 mt-0.5">{activeRooms.length} active spaces</p>
          </div>
        </Card>

        <Card className="p-5 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-violet-500/10 text-violet-400 flex items-center justify-center border border-violet-500/20">
            <Calendar className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-slate-400 font-medium uppercase tracking-wider">Published Schedules</p>
            <h3 className="text-2xl font-bold text-slate-100">
              {drivesLoading ? '-' : drives.filter((d) => d.status === 'published').length}
            </h3>
            <p className="text-[11px] text-slate-500 mt-0.5">Live interview rounds</p>
          </div>
        </Card>
      </div>

      {/* Drives Section */}
      <Card>
        <CardHeader>
          <div>
            <CardTitle>Recruitment Drives</CardTitle>
            <CardDescription>Manage interview windows, stages, candidate enrolment, and schedules</CardDescription>
          </div>
          <Link to="/coordinator/drives">
            <Button variant="ghost" size="sm" rightIcon={<ArrowRight className="w-4 h-4" />}>
              View All Drives
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          {drivesLoading ? (
            <Spinner size="md" label="Loading recruitment drives..." />
          ) : drives.length === 0 ? (
            <EmptyState
              icon={Layers}
              title="No recruitment drives created yet"
              description="Create your first drive to set up interview stages, invite candidates, and run the automated scheduler."
              actionLabel="Create Drive"
              onAction={() => navigate('/coordinator/drives/new')}
            />
          ) : (
            <div className="divide-y divide-surface-border/40">
              {drives.slice(0, 5).map((drive) => (
                <div
                  key={drive.id}
                  className="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-surface-elevated/30 -mx-5 px-5 transition-colors"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <Link
                        to={`/coordinator/drives/${drive.id}`}
                        className="text-sm font-semibold text-slate-100 hover:text-brand-400 transition-colors"
                      >
                        {drive.title}
                      </Link>
                      <Badge variant={driveStatusVariant(drive.status)} size="sm">
                        {drive.status.replace('_', ' ')}
                      </Badge>
                    </div>
                    <p className="text-xs text-slate-400 flex items-center gap-2">
                      <span>Timezone: {drive.timezone}</span>
                      <span>•</span>
                      <span>
                        {new Date(drive.window_start).toLocaleDateString()} — {new Date(drive.window_end).toLocaleDateString()}
                      </span>
                      <span>•</span>
                      <span>{drive.stages?.length || 0} stages</span>
                    </p>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-auto">
                    <Link to={`/coordinator/drives/${drive.id}`}>
                      <Button variant="secondary" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                        Open Drive
                      </Button>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
