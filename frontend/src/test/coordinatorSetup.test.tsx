import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { DriveDetailPage } from '../pages/coordinator/DriveDetailPage';
import { AuthProvider } from '../context/AuthContext';
import { ToastProvider } from '../components/ui/Toast';

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ToastProvider>{children}</ToastProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
};

describe('F2: Coordinator Setup & Locked Fields', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('renders locked banner when drive is published', async () => {
    const mockDrive = {
      id: 'drive-123',
      title: 'Published Placement Drive',
      description: 'Annual placements',
      window_start: '2026-11-01T09:00:00Z',
      window_end: '2026-11-03T18:00:00Z',
      timezone: 'UTC',
      slot_minutes: 30,
      interviewer_buffer_minutes: 10,
      min_round_gap_minutes: 20,
      status: 'published',
      stages: [],
    };

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/drives/drive-123/stages')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => [],
        });
      }
      if (url.includes('/drives/drive-123/candidates')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => [],
        });
      }
      if (url.includes('/users?role=candidate')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => [],
        });
      }
      if (url.includes('/drives/drive-123')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockDrive,
        });
      }
      return Promise.reject(new Error('Unknown url'));
    });

    render(
      <MemoryRouter initialEntries={['/coordinator/drives/drive-123']}>
        <Routes>
          <Route path="/coordinator/drives/:driveId" element={<DriveDetailPage />} />
        </Routes>
      </MemoryRouter>,
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Published Placement Drive' })).toBeInTheDocument();
      expect(
        screen.getByText(/The drive window, timezone, and stage parameters are locked/i)
      ).toBeInTheDocument();
    });
  });

  it('renders stages tab and allows viewing configured stages', async () => {
    const mockDrive = {
      id: 'drive-draft',
      title: 'Draft Placement Drive',
      window_start: '2026-11-01T09:00:00Z',
      window_end: '2026-11-03T18:00:00Z',
      timezone: 'UTC',
      slot_minutes: 45,
      interviewer_buffer_minutes: 15,
      min_round_gap_minutes: 30,
      status: 'draft',
      stages: [],
    };

    const mockStages = [
      {
        id: 'stage-1',
        drive_id: 'drive-draft',
        order_index: 1,
        name: 'Technical Round 1',
        stage_type: 'technical',
        duration_minutes: 45,
        panel_size: 1,
        required_skills: ['python', 'algorithms'],
        rule: { min_score: 7 },
      },
      {
        id: 'stage-2',
        drive_id: 'drive-draft',
        order_index: 2,
        name: 'HR Interview',
        stage_type: 'hr',
        duration_minutes: 30,
        panel_size: 1,
        required_skills: [],
        rule: { min_score: 6 },
      },
    ];

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/drives/drive-draft/stages')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockStages,
        });
      }
      if (url.includes('/drives/drive-draft/candidates')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => [],
        });
      }
      if (url.includes('/users?role=candidate')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => [],
        });
      }
      if (url.includes('/drives/drive-draft')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => mockDrive,
        });
      }
      return Promise.reject(new Error('Unknown url'));
    });

    render(
      <MemoryRouter initialEntries={['/coordinator/drives/drive-draft']}>
        <Routes>
          <Route path="/coordinator/drives/:driveId" element={<DriveDetailPage />} />
        </Routes>
      </MemoryRouter>,
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Draft Placement Drive' })).toBeInTheDocument();
    });

    // Click on Stages tab
    const stagesTab = screen.getByRole('button', { name: /stages/i });
    fireEvent.click(stagesTab);

    await waitFor(() => {
      expect(screen.getByText('Technical Round 1')).toBeInTheDocument();
      expect(screen.getByText('HR Interview')).toBeInTheDocument();
      expect(screen.getByText('python')).toBeInTheDocument();
    });
  });
});
