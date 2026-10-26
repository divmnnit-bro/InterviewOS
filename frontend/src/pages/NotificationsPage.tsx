import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Bell, CheckCheck, Filter, Inbox } from 'lucide-react';
import { apiClient } from '@/api/client';
import { Notification } from '@/types/api';
import { Button, Card, Spinner, EmptyState, Badge } from '@/components/ui';

export const NotificationsPage: React.FC = () => {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const queryClient = useQueryClient();

  const { data: notifications = [], isLoading } = useQuery<Notification[]>({
    queryKey: ['notifications', unreadOnly],
    queryFn: () => apiClient<Notification[]>(`/notifications?unread_only=${unreadOnly}&limit=100`),
  });

  const markReadMutation = useMutation({
    mutationFn: (id: string) => apiClient<Notification>(`/notifications/${id}/read`, { method: 'POST' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  const markAllMutation = useMutation({
    mutationFn: async () => {
      const unread = notifications.filter((n) => !n.is_read);
      await Promise.all(unread.map((n) => apiClient(`/notifications/${n.id}/read`, { method: 'POST' })));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight flex items-center gap-2.5">
            <Bell className="w-6 h-6 text-brand-400" />
            <span>Notification Inbox</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time automated alerts for scheduling, room changes, booking updates, and rescue events
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant={unreadOnly ? 'primary' : 'outline'}
            size="sm"
            onClick={() => setUnreadOnly(!unreadOnly)}
            leftIcon={<Filter className="w-3.5 h-3.5" />}
          >
            {unreadOnly ? 'Showing Unread' : 'Filter Unread'}
          </Button>

          {unreadCount > 0 && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => markAllMutation.mutate()}
              isLoading={markAllMutation.isPending}
              leftIcon={<CheckCheck className="w-3.5 h-3.5 text-brand-400" />}
            >
              Mark all as read
            </Button>
          )}
        </div>
      </div>

      {isLoading ? (
        <Spinner size="lg" label="Loading alerts..." />
      ) : notifications.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={unreadOnly ? 'No unread alerts' : 'Your inbox is clear'}
          description="When drives publish schedules, candidates self-book, or evaluations are submitted, you will see notifications here."
          actionLabel={unreadOnly ? 'Show all notifications' : undefined}
          onAction={unreadOnly ? () => setUnreadOnly(false) : undefined}
        />
      ) : (
        <div className="space-y-3">
          {notifications.map((n) => (
            <Card
              key={n.id}
              className={`p-4 transition-all duration-150 ${
                !n.is_read
                  ? 'bg-surface-elevated/80 border-brand-500/30'
                  : 'bg-surface-card/60 opacity-80'
              }`}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <div
                    className={`w-2.5 h-2.5 rounded-full mt-1.5 shrink-0 ${
                      !n.is_read ? 'bg-brand-400 shadow-sm shadow-brand-400' : 'bg-slate-600'
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <h4 className="text-sm font-semibold text-slate-100">{n.title}</h4>
                      <Badge variant={!n.is_read ? 'brand' : 'neutral'} size="sm">
                        {n.channel}
                      </Badge>
                      <span className="text-[11px] text-slate-500 ml-auto">
                        {new Date(n.created_at).toLocaleString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed whitespace-pre-line">
                      {n.message}
                    </p>
                  </div>
                </div>

                {!n.is_read && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => markReadMutation.mutate(n.id)}
                    title="Mark as read"
                  >
                    <CheckCheck className="w-4 h-4 text-slate-400 hover:text-brand-400" />
                  </Button>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
