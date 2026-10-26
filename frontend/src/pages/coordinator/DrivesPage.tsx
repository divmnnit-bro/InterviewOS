import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Layers, Plus, Calendar, Clock, ArrowRight, Globe } from 'lucide-react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { apiClient, ApiError } from '@/api/client';
import { RecruitmentDrive } from '@/types/api';
import {
  Button,
  Input,
  Textarea,
  Select,
  FormField,
  Modal,
  Card,
  Badge,
  Spinner,
  EmptyState,
  useToast,
} from '@/components/ui';

export const COMMON_TIMEZONES = [
  'UTC',
  'Asia/Kolkata',
  'America/New_York',
  'America/Los_Angeles',
  'America/Chicago',
  'Europe/London',
  'Europe/Paris',
  'Europe/Berlin',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Asia/Dubai',
  'Australia/Sydney',
];

export const DrivesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { success, error: toastError } = useToast();
  const location = useLocation();
  const navigate = useNavigate();

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  // Form states
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [windowStart, setWindowStart] = useState('');
  const [windowEnd, setWindowEnd] = useState('');
  const [timezone, setTimezone] = useState(
    Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Kolkata'
  );
  const [slotMinutes, setSlotMinutes] = useState(45);
  const [bufferMinutes, setBufferMinutes] = useState(15);
  const [roundGapMinutes, setRoundGapMinutes] = useState(30);

  const { data: drives = [], isLoading } = useQuery<RecruitmentDrive[]>({
    queryKey: ['drives'],
    queryFn: () => apiClient<RecruitmentDrive[]>('/drives'),
  });

  const createDriveMutation = useMutation({
    mutationFn: (body: any) =>
      apiClient<RecruitmentDrive>('/drives', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: (newDrive) => {
      success('Drive Created', `"${newDrive.title}" has been initialized in Draft mode`);
      queryClient.invalidateQueries({ queryKey: ['drives'] });
      setIsCreateModalOpen(false);
      resetForm();
    },
    onError: (err: any) => {
      if (err instanceof ApiError) {
        toastError('Failed to Create Drive', err.message);
      } else {
        toastError('Error', 'An unexpected error occurred.');
      }
    },
  });

  const resetForm = () => {
    setTitle('');
    setDescription('');
    setWindowStart('');
    setWindowEnd('');
    setSlotMinutes(45);
    setBufferMinutes(15);
    setRoundGapMinutes(30);
  };

  const handleOpenCreate = () => {
    // Default window: tomorrow 09:00 to 3 days later 18:00
    const now = new Date();
    const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 9, 0);
    const endDay = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 3, 18, 0);

    const toLocalISO = (d: Date) => {
      const pad = (n: number) => String(n).padStart(2, '0');
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    };

    setWindowStart(toLocalISO(tomorrow));
    setWindowEnd(toLocalISO(endDay));
    setIsCreateModalOpen(true);
  };

  // /coordinator/drives/new opens the create dialog on the drives list instead of
  // being mistaken for a drive id.
  useEffect(() => {
    if (location.pathname.endsWith('/drives/new')) {
      handleOpenCreate();
      navigate('/coordinator/drives', { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  const handleSubmitCreate = (e: React.FormEvent) => {
    e.preventDefault();

    if (!windowStart || !windowEnd) {
      toastError('Validation Error', 'Start and end windows are required');
      return;
    }

    createDriveMutation.mutate({
      title,
      description: description || null,
      window_start: new Date(windowStart).toISOString(),
      window_end: new Date(windowEnd).toISOString(),
      timezone,
      slot_minutes: Number(slotMinutes),
      interviewer_buffer_minutes: Number(bufferMinutes),
      min_round_gap_minutes: Number(roundGapMinutes),
    });
  };

  const statusVariant = (status: string): 'brand' | 'success' | 'warning' | 'danger' | 'neutral' => {
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
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight flex items-center gap-2.5">
            <Layers className="w-6 h-6 text-brand-400" />
            <span>Recruitment Drives</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            End-to-end multi-round hiring drives with automated constraint solving and ripple rescue
          </p>
        </div>

        <Button variant="primary" size="sm" onClick={handleOpenCreate} leftIcon={<Plus className="w-4 h-4" />}>
          New Drive
        </Button>
      </div>

      {isLoading ? (
        <Spinner size="lg" label="Loading drives..." />
      ) : drives.length === 0 ? (
        <EmptyState
          icon={Layers}
          title="No recruitment drives found"
          description="Create your first drive to define stages, configure interview slots, and run scheduling."
          actionLabel="Create First Drive"
          onAction={handleOpenCreate}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {drives.map((drive) => (
            <Card
              key={drive.id}
              className="flex flex-col justify-between hover:border-brand-500/40 hover:shadow-lg transition-all"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-3">
                  <h3 className="text-base font-bold text-slate-100 leading-snug line-clamp-1">{drive.title}</h3>
                  <Badge variant={statusVariant(drive.status)} size="sm">
                    {drive.status.replace('_', ' ')}
                  </Badge>
                </div>

                {drive.description && (
                  <p className="text-xs text-slate-400 line-clamp-2 mb-4 leading-relaxed">
                    {drive.description}
                  </p>
                )}

                <div className="space-y-2 text-xs text-slate-300 bg-surface-elevated/60 p-3 rounded-xl border border-surface-border">
                  <div className="flex items-center gap-2">
                    <Calendar className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                    <span>
                      {new Date(drive.window_start).toLocaleDateString()} —{' '}
                      {new Date(drive.window_end).toLocaleDateString()}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <Globe className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                    <span className="font-mono text-[11px]">{drive.timezone}</span>
                  </div>

                  <div className="flex items-center gap-2">
                    <Clock className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                    <span>
                      Slot: {drive.slot_minutes}m • Buffer: {drive.interviewer_buffer_minutes}m • Gap:{' '}
                      {drive.min_round_gap_minutes}m
                    </span>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-surface-border/60 mt-4 flex items-center justify-between">
                <span className="text-xs text-slate-400 font-medium">
                  {drive.stages?.length || 0} stages configured
                </span>
                <Link to={`/coordinator/drives/${drive.id}`}>
                  <Button variant="secondary" size="sm" rightIcon={<ArrowRight className="w-3.5 h-3.5" />}>
                    Manage
                  </Button>
                </Link>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create Drive Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create Recruitment Drive"
        description="Establish the global drive window, timezone, and solver parameters"
        maxWidth="lg"
      >
        <form onSubmit={handleSubmitCreate} className="space-y-4">
          <FormField label="Drive Title" required>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Autumn 2026 Campus Placement"
              required
            />
          </FormField>

          <FormField label="Description">
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Drive scope, hiring teams, and applicant guidelines..."
              rows={2}
            />
          </FormField>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <FormField label="Drive Window Start" required>
              <Input
                type="datetime-local"
                value={windowStart}
                onChange={(e) => setWindowStart(e.target.value)}
                required
              />
            </FormField>

            <FormField label="Drive Window End" required>
              <Input
                type="datetime-local"
                value={windowEnd}
                onChange={(e) => setWindowEnd(e.target.value)}
                required
              />
            </FormField>
          </div>

          <FormField label="Drive Timezone (IANA)" required hint="All solver times and candidate booking slots will align with this timezone">
            <Select value={timezone} onChange={(e) => setTimezone(e.target.value)}>
              {COMMON_TIMEZONES.map((tz) => (
                <option key={tz} value={tz}>
                  {tz}
                </option>
              ))}
            </Select>
          </FormField>

          <div className="p-4 rounded-xl bg-surface-elevated/70 border border-surface-border space-y-3">
            <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
              <Clock className="w-4 h-4 text-brand-400" />
              <span>Solver Rules &amp; Cadence</span>
            </h4>

            <div className="grid grid-cols-3 gap-3">
              <FormField label="Slot (mins)" required hint="Default duration">
                <Input
                  type="number"
                  min={15}
                  max={240}
                  step={5}
                  value={slotMinutes}
                  onChange={(e) => setSlotMinutes(parseInt(e.target.value, 10))}
                  required
                />
              </FormField>

              <FormField label="Buffer (mins)" required hint="Between interviews">
                <Input
                  type="number"
                  min={0}
                  max={120}
                  step={5}
                  value={bufferMinutes}
                  onChange={(e) => setBufferMinutes(parseInt(e.target.value, 10))}
                  required
                />
              </FormField>

              <FormField label="Round Gap (mins)" required hint="Candidate rest">
                <Input
                  type="number"
                  min={0}
                  max={240}
                  step={5}
                  value={roundGapMinutes}
                  onChange={(e) => setRoundGapMinutes(parseInt(e.target.value, 10))}
                  required
                />
              </FormField>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-surface-border">
            <Button type="button" variant="outline" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={createDriveMutation.isPending}>
              Create Drive
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
