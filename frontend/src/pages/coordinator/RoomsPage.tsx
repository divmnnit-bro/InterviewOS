import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Building, Plus, Edit2, MapPin, Users, CheckCircle, XCircle, Clock } from 'lucide-react';
import { Link } from 'react-router-dom';
import { apiClient, ApiError } from '@/api/client';
import { Room } from '@/types/api';
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

export const RoomsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { success, error: toastError } = useToast();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingRoom, setEditingRoom] = useState<Room | null>(null);

  const [name, setName] = useState('');
  const [capacity, setCapacity] = useState(1);
  const [location, setLocation] = useState('');
  const [isActive, setIsActive] = useState(true);

  const { data: rooms = [], isLoading } = useQuery<Room[]>({
    queryKey: ['rooms'],
    queryFn: () => apiClient<Room[]>('/rooms'),
  });

  const saveMutation = useMutation({
    mutationFn: (body: any) => {
      if (editingRoom) {
        return apiClient<Room>(`/rooms/${editingRoom.id}`, {
          method: 'PATCH',
          body: JSON.stringify(body),
        });
      }
      return apiClient<Room>('/rooms', {
        method: 'POST',
        body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      success(editingRoom ? 'Room Updated' : 'Room Created', 'Room configuration saved successfully');
      queryClient.invalidateQueries({ queryKey: ['rooms'] });
      handleCloseModal();
    },
    onError: (err: any) => {
      if (err instanceof ApiError) {
        toastError('Error', err.message);
      } else {
        toastError('Error', 'Failed to save room');
      }
    },
  });

  const toggleStatusMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      apiClient<Room>(`/rooms/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active }),
      }),
    onSuccess: (updated) => {
      success('Status Changed', `Room is now ${updated.is_active ? 'active' : 'inactive'}`);
      queryClient.invalidateQueries({ queryKey: ['rooms'] });
    },
    onError: (err: any) => {
      toastError('Error', err.message || 'Failed to toggle status');
    },
  });

  const handleOpenCreate = () => {
    setEditingRoom(null);
    setName('');
    setCapacity(1);
    setLocation('');
    setIsActive(true);
    setIsModalOpen(true);
  };

  const handleOpenEdit = (room: Room) => {
    setEditingRoom(room);
    setName(room.name);
    setCapacity(room.capacity);
    setLocation(room.location || '');
    setIsActive(room.is_active);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingRoom(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    saveMutation.mutate({
      name,
      capacity: Number(capacity),
      location: location || null,
      is_active: isActive,
    });
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight flex items-center gap-2.5">
            <Building className="w-6 h-6 text-brand-400" />
            <span>Interview Rooms &amp; Spaces</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Physical or virtual interview venues with room availability windows and capacity rules
          </p>
        </div>

        <Button variant="primary" size="sm" onClick={handleOpenCreate} leftIcon={<Plus className="w-4 h-4" />}>
          Add Room
        </Button>
      </div>

      {/* Grid */}
      {isLoading ? (
        <Spinner size="lg" label="Loading rooms..." />
      ) : rooms.length === 0 ? (
        <EmptyState
          icon={Building}
          title="No interview rooms configured"
          description="Rooms represent interview spaces where scheduled sessions are hosted. Add your first room."
          actionLabel="Add Room"
          onAction={handleOpenCreate}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {rooms.map((room) => (
            <Card key={room.id} className="flex flex-col justify-between hover:border-surface-hover transition-colors">
              <div>
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div>
                    <h3 className="text-base font-bold text-slate-100">{room.name}</h3>
                    {room.location && (
                      <p className="text-xs text-slate-400 flex items-center gap-1 mt-0.5">
                        <MapPin className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                        <span>{room.location}</span>
                      </p>
                    )}
                  </div>
                  <Badge variant={room.is_active ? 'success' : 'neutral'} size="sm">
                    {room.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>

                <div className="flex items-center gap-3 py-2 text-xs text-slate-300">
                  <div className="flex items-center gap-1.5">
                    <Users className="w-3.5 h-3.5 text-slate-500" />
                    <span>Capacity: {room.capacity} simultaneous interviews</span>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-surface-border/60 mt-4 flex items-center justify-between gap-2">
                <Link to={`/coordinator/rooms/${room.id}/availability`}>
                  <Button variant="outline" size="sm" leftIcon={<Clock className="w-3.5 h-3.5" />}>
                    Availability
                  </Button>
                </Link>

                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleStatusMutation.mutate({ id: room.id, is_active: !room.is_active })}
                    title={room.is_active ? 'Deactivate room' : 'Activate room'}
                  >
                    {room.is_active ? (
                      <XCircle className="w-4 h-4 text-slate-400 hover:text-amber-400" />
                    ) : (
                      <CheckCircle className="w-4 h-4 text-slate-400 hover:text-emerald-400" />
                    )}
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => handleOpenEdit(room)}>
                    <Edit2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        title={editingRoom ? 'Edit Room' : 'Add New Room'}
        description="Configure space name, capacity, and status"
        maxWidth="sm"
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          <FormField label="Room Name" required>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Lab 402, Boardroom A"
              required
            />
          </FormField>

          <FormField label="Simultaneous Capacity" required hint="Number of parallel interviews allowed">
            <Input
              type="number"
              min={1}
              max={20}
              value={capacity}
              onChange={(e) => setCapacity(parseInt(e.target.value, 10))}
              required
            />
          </FormField>

          <FormField label="Location / Details" hint="Building, floor, or virtual meeting platform">
            <Input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. Building C, 3rd Floor"
            />
          </FormField>

          <div className="flex items-center gap-2 pt-1">
            <input
              type="checkbox"
              id="isActiveCheck"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="rounded bg-surface-elevated border-surface-border text-brand-600 focus:ring-brand-500 w-4 h-4"
            />
            <label htmlFor="isActiveCheck" className="text-xs text-slate-200 cursor-pointer font-medium">
              Room is currently active and available for scheduling
            </label>
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-surface-border">
            <Button type="button" variant="outline" onClick={handleCloseModal}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={saveMutation.isPending}>
              {editingRoom ? 'Save Changes' : 'Create Room'}
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
