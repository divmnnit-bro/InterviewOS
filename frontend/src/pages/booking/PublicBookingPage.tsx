import React, { useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Sparkles,
  AlertCircle,
  Calendar,
  Clock,
  CheckCircle2,
  Download,
  RefreshCw,
  Globe,
  ArrowRight,
} from 'lucide-react';
import { apiClient, generateIdempotencyKey } from '@/api/client';
import { BookingOffers } from '@/types/api';
import { Card, Spinner, Badge, Button } from '@/components/ui';
import { groupByDay, formatTimeUTC } from '@/lib/timelineMath';

export interface BookedInterview {
  id: string;
  drive_id: string;
  stage_id: string;
  candidate_id: string;
  room_id?: string;
  start_time: string;
  end_time: string;
  status: string;
}

export const PublicBookingPage: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const queryClient = useQueryClient();

  const [selectedSlot, setSelectedSlot] = useState<{ start: string; end: string } | null>(null);
  const [confirmedBooking, setConfirmedBooking] = useState<BookedInterview | null>(null);
  const [conflictError, setConflictError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [activeDayIndex, setActiveDayIndex] = useState<number>(0);

  // Maintain idempotency key per confirmation attempt
  const idempotencyKeyRef = useRef<string>(generateIdempotencyKey());

  const {
    data: offers,
    isLoading,
    error,
    refetch,
    isRefetching,
  } = useQuery<BookingOffers>({
    queryKey: ['booking-offers', token],
    queryFn: () => apiClient<BookingOffers>(`/booking/${token}`, { isPublic: true }),
    enabled: !!token,
    retry: false,
  });

  const confirmMutation = useMutation({
    mutationFn: async (slotStart: string) => {
      // Sends Idempotency-Key header on public booking endpoint
      return await apiClient<BookedInterview>(`/booking/${token}/confirm`, {
        method: 'POST',
        isPublic: true,
        idempotencyKey: idempotencyKeyRef.current,
        body: JSON.stringify({ start: slotStart }),
      });
    },
    onSuccess: (data) => {
      setConfirmedBooking(data);
      setConflictError(null);
      setValidationError(null);
      queryClient.invalidateQueries({ queryKey: ['booking-offers', token] });
    },
    onError: (err: any) => {
      if (err.status === 409) {
        setConflictError(
          'That slot was just booked by another candidate or is no longer available. We have refreshed the available slots for you.'
        );
        setSelectedSlot(null);
        // Refresh idempotency key for next slot choice
        idempotencyKeyRef.current = generateIdempotencyKey();
        refetch();
      } else if (err.status === 422) {
        setValidationError(err.message || 'Validation error while booking slot.');
      } else {
        setConflictError(err.message || 'An unexpected error occurred. Please try another slot.');
      }
    },
  });

  const handleSelectSlot = (slot: { start: string; end: string }) => {
    setSelectedSlot(slot);
    setConflictError(null);
    setValidationError(null);
    // Fresh idempotency key for new slot selection
    idempotencyKeyRef.current = generateIdempotencyKey();
  };

  const handleConfirm = () => {
    if (!selectedSlot) return;
    confirmMutation.mutate(selectedSlot.start);
  };

  // Group slots by day
  const slotsGrouped = offers?.slots
    ? groupByDay(offers.slots.map((s) => ({ ...s, startTime: s.start })))
    : [];

  const currentDayGroup = slotsGrouped[activeDayIndex] || slotsGrouped[0];

  const icsDownloadUrl = `${apiClient.getBaseUrl()}/booking/${token}/ics`;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4 sm:p-6">
      <div className="max-w-2xl w-full space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-600 to-violet-500 text-white shadow-xl shadow-indigo-500/25 mb-1">
            <Sparkles className="w-6 h-6" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
            Interview Self-Booking
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 max-w-md mx-auto">
            Choose your preferred time slot for your upcoming interview round.
          </p>
        </div>

        {/* Loading State */}
        {isLoading ? (
          <Card className="p-12 text-center bg-slate-900 border-slate-800">
            <Spinner size="lg" className="mx-auto mb-3" />
            <p className="text-slate-400 text-sm">Checking available interview slots...</p>
          </Card>
        ) : error ? (
          /* Error State: 401 or Invalid Link */
          <Card className="p-8 text-center border-rose-500/30 bg-slate-900">
            <div className="w-12 h-12 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center justify-center mx-auto mb-3">
              <AlertCircle className="w-6 h-6" />
            </div>
            <h3 className="text-base font-bold text-slate-100">Booking Link Expired or Invalid</h3>
            <p className="text-xs text-slate-400 mt-1 max-w-md mx-auto">
              {(error as any)?.message ||
                'This invitation link is invalid or has reached its expiration time. Please contact your recruitment coordinator to receive a new booking link.'}
            </p>
          </Card>
        ) : confirmedBooking || offers?.booked ? (
          /* Confirmation / Already Booked State */
          <Card className="p-8 text-center bg-slate-900 border-emerald-500/30 space-y-5">
            <div className="w-14 h-14 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <div>
              <Badge variant="success" className="mb-2">
                Interview Confirmed
              </Badge>
              <h2 className="text-xl font-bold text-slate-100">You're All Set!</h2>
              <p className="text-xs text-slate-400 mt-1">
                Your interview slot has been successfully scheduled.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 text-left space-y-2.5 max-w-md mx-auto">
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Round:</span>
                <span className="font-semibold text-slate-200">{offers?.stage_name}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Duration:</span>
                <span className="font-semibold text-slate-200">{offers?.duration_minutes} Minutes</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Timezone:</span>
                <span className="font-mono text-slate-300">{offers?.timezone}</span>
              </div>
              <div className="flex items-center justify-between text-xs pt-2 border-t border-slate-800/80">
                <span className="text-slate-400">Confirmed Slot:</span>
                <span className="font-mono font-bold text-indigo-300">
                  {offers?.booked
                    ? new Date(offers.booked.start).toLocaleString([], {
                        weekday: 'short',
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    : selectedSlot
                    ? new Date(selectedSlot.start).toLocaleString([], {
                        weekday: 'short',
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })
                    : ''}
                </span>
              </div>
            </div>

            <div className="pt-2">
              <a
                href={icsDownloadUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/25 transition-all"
              >
                <Download className="w-4 h-4" />
                Add to Calendar (.ics)
              </a>
            </div>
          </Card>
        ) : offers ? (
          /* Slot Selection View */
          <Card className="p-6 bg-slate-900 border-slate-800 space-y-6">
            {/* Round & Drive Banner */}
            <div className="border-b border-slate-800 pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-indigo-400">
                  Scheduled Stage
                </span>
                <h2 className="text-lg font-bold text-slate-100">{offers.stage_name}</h2>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="brand" className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {offers.duration_minutes} Mins
                </Badge>
                <Badge variant="neutral" className="flex items-center gap-1 font-mono text-[11px]">
                  <Globe className="w-3 h-3 text-slate-400" />
                  {offers.timezone}
                </Badge>
              </div>
            </div>

            {/* Conflict Alert (409) */}
            {conflictError && (
              <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
                <p className="text-xs text-amber-200/90 leading-relaxed">{conflictError}</p>
              </div>
            )}

            {/* Validation Error (422) */}
            {validationError && (
              <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-2.5">
                <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                <p className="text-xs text-rose-200/90 leading-relaxed">{validationError}</p>
              </div>
            )}

            {/* Slots Area */}
            {offers.slots.length === 0 ? (
              <div className="text-center py-10 space-y-3">
                <div className="w-12 h-12 rounded-full bg-slate-800 text-slate-400 flex items-center justify-center mx-auto">
                  <Calendar className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-semibold text-slate-200">No Free Slots Available</h4>
                <p className="text-xs text-slate-400 max-w-sm mx-auto">
                  All current time blocks are filled. Please click below to refresh or check back shortly.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => refetch()}
                  disabled={isRefetching}
                  className="border-slate-700 text-slate-300"
                >
                  <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${isRefetching ? 'animate-spin' : ''}`} />
                  Refresh Slots
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Day Tabs */}
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                    Available Days
                  </span>
                  <button
                    onClick={() => refetch()}
                    disabled={isRefetching}
                    className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1"
                  >
                    <RefreshCw className={`w-3 h-3 ${isRefetching ? 'animate-spin' : ''}`} />
                    Refresh
                  </button>
                </div>

                <div className="flex items-center gap-2 overflow-x-auto pb-1 max-w-full">
                  {slotsGrouped.map((day, idx) => (
                    <button
                      key={day.dateStr}
                      onClick={() => setActiveDayIndex(idx)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-all whitespace-nowrap ${
                        activeDayIndex === idx
                          ? 'bg-indigo-600 border-indigo-500 text-white shadow-sm'
                          : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      {day.label} ({day.items.length})
                    </button>
                  ))}
                </div>

                {/* Slots Grid for Selected Day */}
                {currentDayGroup && (
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 pt-2">
                    {currentDayGroup.items.map((slot, idx) => {
                      const isSelected = selectedSlot?.start === slot.start;
                      const startTimeFormatted = formatTimeUTC(slot.start);
                      const endTimeFormatted = formatTimeUTC(slot.end);

                      return (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => handleSelectSlot(slot)}
                          className={`p-3 rounded-xl border text-center transition-all flex flex-col items-center justify-center gap-1 ${
                            isSelected
                              ? 'bg-indigo-600/20 border-indigo-500 ring-2 ring-indigo-500/40 text-white shadow-md'
                              : 'bg-slate-950/60 border-slate-800 text-slate-300 hover:border-slate-700 hover:bg-slate-900'
                          }`}
                        >
                          <span className="text-xs font-mono font-bold">
                            {startTimeFormatted} - {endTimeFormatted}
                          </span>
                          <span
                            className={`text-[10px] font-medium ${
                              isSelected ? 'text-indigo-300' : 'text-slate-500'
                            }`}
                          >
                            {isSelected ? 'Selected' : 'Available'}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* Confirm Action Bar */}
                <div className="pt-4 border-t border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="text-xs text-slate-400">
                    {selectedSlot ? (
                      <span>
                        Selected Slot:{' '}
                        <strong className="text-indigo-300 font-mono">
                          {formatTimeUTC(selectedSlot.start)} - {formatTimeUTC(selectedSlot.end)}
                        </strong>
                      </span>
                    ) : (
                      'Please pick an available time slot above to confirm.'
                    )}
                  </div>
                  <Button
                    variant="primary"
                    disabled={!selectedSlot || confirmMutation.isPending}
                    onClick={handleConfirm}
                    className="bg-indigo-600 hover:bg-indigo-500 min-w-[140px]"
                  >
                    {confirmMutation.isPending ? (
                      <>
                        <Spinner size="sm" className="mr-2" />
                        Confirming...
                      </>
                    ) : (
                      <>
                        Confirm Slot
                        <ArrowRight className="w-4 h-4 ml-1.5" />
                      </>
                    )}
                  </Button>
                </div>
              </div>
            )}
          </Card>
        ) : null}
      </div>
    </div>
  );
};
