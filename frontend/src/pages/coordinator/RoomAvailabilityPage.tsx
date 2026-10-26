import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import { apiClient } from '@/api/client';
import { Room } from '@/types/api';
import { AvailabilityEditor } from '@/components/availability/AvailabilityEditor';
import { Spinner, EmptyState } from '@/components/ui';

export const RoomAvailabilityPage: React.FC = () => {
  const { roomId } = useParams<{ roomId: string }>();

  const { data: room, isLoading } = useQuery<Room>({
    queryKey: ['room', roomId],
    queryFn: async () => {
      const rooms = await apiClient<Room[]>('/rooms');
      const found = rooms.find((r) => r.id === roomId);
      if (!found) throw new Error('Room not found');
      return found;
    },
    enabled: !!roomId,
  });

  if (isLoading) return <Spinner size="lg" label="Loading room details..." />;

  if (!room) {
    return (
      <EmptyState
        title="Room Not Found"
        description="The requested interview space could not be located."
      />
    );
  }

  return (
    <div className="space-y-6">
      <Link
        to="/coordinator/rooms"
        className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>Back to Rooms</span>
      </Link>

      <AvailabilityEditor
        ownerId={room.id}
        ownerType="room"
        ownerName={room.name}
      />
    </div>
  );
};
