import React from 'react';
import { useAuth } from '@/context/AuthContext';
import { AvailabilityEditor } from '@/components/availability/AvailabilityEditor';

export const CandidateAvailabilityPage: React.FC = () => {
  const { user } = useAuth();

  if (!user) return null;

  return (
    <div className="space-y-6">
      <AvailabilityEditor
        ownerId={user.id}
        ownerType="user"
        ownerName={user.name}
      />
    </div>
  );
};
