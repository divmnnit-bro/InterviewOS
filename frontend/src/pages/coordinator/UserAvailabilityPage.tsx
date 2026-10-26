import React from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import { apiClient } from '@/api/client';
import { User } from '@/types/api';
import { AvailabilityEditor } from '@/components/availability/AvailabilityEditor';
import { Spinner, EmptyState } from '@/components/ui';

export const UserAvailabilityPage: React.FC = () => {
  const { userId } = useParams<{ userId: string }>();

  const { data: user, isLoading } = useQuery<User>({
    queryKey: ['user', userId],
    queryFn: async () => {
      const users = await apiClient<User[]>('/users');
      const found = users.find((u) => u.id === userId);
      if (!found) throw new Error('User not found');
      return found;
    },
    enabled: !!userId,
  });

  if (isLoading) return <Spinner size="lg" label="Loading user details..." />;

  if (!user) {
    return (
      <EmptyState
        title="User Not Found"
        description="The requested candidate or interviewer could not be located."
      />
    );
  }

  return (
    <div className="space-y-6">
      <Link
        to="/coordinator/people"
        className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        <span>Back to People</span>
      </Link>

      <AvailabilityEditor
        ownerId={user.id}
        ownerType="user"
        ownerName={`${user.name} (${user.role})`}
      />
    </div>
  );
};
