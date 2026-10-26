import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Clock,
  Plus,
  Trash2,
  Calendar,
  AlertCircle,
  Save,
  Info,
  CalendarDays,
} from 'lucide-react';
import { apiClient, ApiError } from '@/api/client';
import { WindowTime, AvailabilityOut } from '@/types/api';
import { mergeOverlappingWindows, clipToDriveWindow, isValidWindow } from '@/lib/availabilityMath';
import {
  Button,
  Input,
  FormField,
  Modal,
  Card,
  Badge,
  Spinner,
  EmptyState,
  useToast,
} from '@/components/ui';

export interface AvailabilityEditorProps {
  ownerId: string;
  ownerType: 'user' | 'room';
  ownerName: string;
  driveWindow?: {
    start: string;
    end: string;
    timezone: string;
    title?: string;
  };
  readOnly?: boolean;
}

export const AvailabilityEditor: React.FC<AvailabilityEditorProps> = ({
  ownerId,
  ownerType,
  ownerName,
  driveWindow,
  readOnly = false,
}) => {
  const queryClient = useQueryClient();
  const { success, error: toastError } = useToast();

  const endpoint = ownerType === 'room' ? `/rooms/${ownerId}/availability` : `/users/${ownerId}/availability`;

  const { data, isLoading } = useQuery<AvailabilityOut>({
    queryKey: ['availability', ownerType, ownerId],
    queryFn: () => apiClient<AvailabilityOut>(endpoint),
    enabled: !!ownerId,
  });

  const [windows, setWindows] = useState<WindowTime[]>([]);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [newDate, setNewDate] = useState('');
  const [newStartTime, setNewStartTime] = useState('09:00');
  const [newEndTime, setNewEndTime] = useState('17:00');
  const [formError, setFormError] = useState<string | null>(null);

  // Sync windows from API query
  useEffect(() => {
    if (data?.windows) {
      setWindows(data.windows);
    }
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: (windowsToSave: WindowTime[]) =>
      apiClient<AvailabilityOut>(endpoint, {
        method: 'PUT',
        body: JSON.stringify({ windows: windowsToSave }),
      }),
    onSuccess: (res) => {
      setWindows(res.windows);
      success('Availability Saved', 'Your available schedule windows have been updated.');
      queryClient.invalidateQueries({ queryKey: ['availability', ownerType, ownerId] });
    },
    onError: (err: any) => {
      if (err instanceof ApiError) {
        toastError('Failed to Save', err.message);
      } else {
        toastError('Error', 'Failed to update availability.');
      }
    },
  });

  const handleOpenAdd = () => {
    // Default date to drive window start or tomorrow
    let defaultDate = new Date();
    if (driveWindow?.start) {
      defaultDate = new Date(driveWindow.start);
    } else {
      defaultDate.setDate(defaultDate.getDate() + 1);
    }
    const yyyy = defaultDate.getFullYear();
    const mm = String(defaultDate.getMonth() + 1).padStart(2, '0');
    const dd = String(defaultDate.getDate()).padStart(2, '0');

    setNewDate(`${yyyy}-${mm}-${dd}`);
    setNewStartTime('09:00');
    setNewEndTime('17:00');
    setFormError(null);
    setIsAddModalOpen(true);
  };

  const handleAddWindow = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const startISO = new Date(`${newDate}T${newStartTime}:00`).toISOString();
    const endISO = new Date(`${newDate}T${newEndTime}:00`).toISOString();

    if (!isValidWindow(startISO, endISO)) {
      setFormError('End time must be after start time.');
      return;
    }

    const updated = [...windows, { start_time: startISO, end_time: endISO }];
    const merged = mergeOverlappingWindows(updated);
    setWindows(merged);
    setIsAddModalOpen(false);
  };

  const handleDeleteWindow = (index: number) => {
    const updated = windows.filter((_, i) => i !== index);
    setWindows(updated);
  };

  const handleSaveAll = () => {
    const merged = mergeOverlappingWindows(windows);
    saveMutation.mutate(merged);
  };

  const handleClipToDrive = () => {
    if (!driveWindow) return;
    const clipped = clipToDriveWindow(windows, driveWindow.start, driveWindow.end);
    setWindows(clipped);
    success('Windows Clipped', 'Availability windows trimmed to match the drive start and end dates.');
  };

  // Group windows by Date string for clear agenda/calendar viewing
  const groupedWindows: Record<string, WindowTime[]> = {};
  windows.forEach((w) => {
    const dStr = new Date(w.start_time).toLocaleDateString(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
    if (!groupedWindows[dStr]) groupedWindows[dStr] = [];
    groupedWindows[dStr].push(w);
  });

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Clock className="w-5 h-5 text-brand-400" />
            <span>Availability: {ownerName}</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Define available time windows for scheduling. Overlapping blocks are automatically merged on save.
          </p>
        </div>

        {!readOnly && (
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleOpenAdd} leftIcon={<Plus className="w-4 h-4" />}>
              Add Window
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSaveAll}
              isLoading={saveMutation.isPending}
              leftIcon={<Save className="w-4 h-4" />}
            >
              Save Changes
            </Button>
          </div>
        )}
      </div>

      {/* Room Rule Banner */}
      {ownerType === 'room' && (
        <div className="p-4 rounded-xl bg-surface-elevated border border-surface-border flex items-start gap-3">
          <Info className="w-5 h-5 text-brand-400 shrink-0 mt-0.5" />
          <div className="text-xs text-slate-300">
            <p className="font-semibold text-slate-100 mb-0.5">Room Availability Rule:</p>
            <p>
              Rooms with <span className="font-semibold text-brand-300">no defined windows</span> are considered open and available for the entire drive duration. You only need to add windows if the room has restricted access or scheduled maintenance.
            </p>
          </div>
        </div>
      )}

      {/* Drive Window Reference */}
      {driveWindow && (
        <div className="p-4 rounded-xl bg-brand-500/5 border border-brand-500/20 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 text-slate-300">
            <Calendar className="w-4 h-4 text-brand-400" />
            <span>
              Target Drive Window ({driveWindow.title || 'Recruitment'}):{' '}
              <strong className="text-slate-100">
                {new Date(driveWindow.start).toLocaleDateString()} — {new Date(driveWindow.end).toLocaleDateString()}
              </strong>{' '}
              ({driveWindow.timezone})
            </span>
          </div>

          {!readOnly && windows.length > 0 && (
            <Button variant="ghost" size="sm" onClick={handleClipToDrive} className="text-xs text-brand-300 self-start sm:self-auto">
              Clip windows to drive
            </Button>
          )}
        </div>
      )}

      {/* Agenda / Calendar of Windows */}
      {isLoading ? (
        <Spinner size="lg" label="Loading availability windows..." />
      ) : windows.length === 0 ? (
        <EmptyState
          icon={CalendarDays}
          title="No availability windows registered"
          description={
            ownerType === 'room'
              ? 'This room is fully open and unconstrained throughout the drive window.'
              : 'Add your free time slots so the scheduler can match your interviews without conflicts.'
          }
          actionLabel={!readOnly ? 'Add Availability Window' : undefined}
          onAction={handleOpenAdd}
        />
      ) : (
        <div className="space-y-4">
          {Object.entries(groupedWindows).map(([dateLabel, slots]) => (
            <Card key={dateLabel} className="p-4">
              <div className="flex items-center justify-between pb-3 border-b border-surface-border/60 mb-3">
                <span className="text-sm font-bold text-slate-200 flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-brand-400" />
                  <span>{dateLabel}</span>
                </span>
                <Badge variant="neutral" size="sm">
                  {slots.length} window{slots.length > 1 ? 's' : ''}
                </Badge>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {slots.map((slot, idx) => {
                  const globalIdx = windows.indexOf(slot);
                  const startTime = new Date(slot.start_time).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  });
                  const endTime = new Date(slot.end_time).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  });

                  return (
                    <div
                      key={idx}
                      className="p-3 rounded-lg bg-surface-elevated/70 border border-surface-border flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <Clock className="w-3.5 h-3.5 text-emerald-400" />
                        <span className="font-semibold text-slate-200">
                          {startTime} — {endTime}
                        </span>
                      </div>

                      {!readOnly && (
                        <button
                          type="button"
                          onClick={() => handleDeleteWindow(globalIdx)}
                          className="text-slate-500 hover:text-rose-400 transition-colors p-1"
                          title="Remove window"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Add Window Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="Add Available Time Window"
        description="Select date and active start/end hours"
        maxWidth="sm"
      >
        <form onSubmit={handleAddWindow} className="space-y-4">
          {formError && (
            <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{formError}</span>
            </div>
          )}

          <FormField label="Date" required>
            <Input
              type="date"
              value={newDate}
              onChange={(e) => setNewDate(e.target.value)}
              required
            />
          </FormField>

          <div className="grid grid-cols-2 gap-3">
            <FormField label="Start Time" required>
              <Input
                type="time"
                value={newStartTime}
                onChange={(e) => setNewStartTime(e.target.value)}
                required
              />
            </FormField>

            <FormField label="End Time" required>
              <Input
                type="time"
                value={newEndTime}
                onChange={(e) => setNewEndTime(e.target.value)}
                required
              />
            </FormField>
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-surface-border">
            <Button type="button" variant="outline" onClick={() => setIsAddModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary">
              Add Window
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
