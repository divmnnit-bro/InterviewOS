import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { setStoredToken } from '../api/client';

const TestComponent: React.FC = () => {
  const { user, role, isAuthenticated, isLoading, logout, login } = useAuth();

  if (isLoading) return <div>Loading...</div>;

  return (
    <div>
      <div data-testid="auth-status">{isAuthenticated ? 'authenticated' : 'unauthenticated'}</div>
      <div data-testid="user-role">{role || 'none'}</div>
      <div data-testid="user-name">{user?.name || 'none'}</div>
      <button onClick={() => login('coord@example.com', 'password123')}>Login</button>
      <button onClick={logout}>Logout</button>
    </div>
  );
};

describe('AuthContext and Session Restoration', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('initializes as unauthenticated when no token in localStorage', async () => {
    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('unauthenticated');
      expect(screen.getByTestId('user-role')).toHaveTextContent('none');
    });
  });

  it('restores session when valid token exists in storage', async () => {
    setStoredToken('valid-token');

    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/auth/me')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          headers: new Headers({ 'content-type': 'application/json' }),
          json: async () => ({
            id: 'u-1',
            name: 'Sarah Coordinator',
            email: 'coord@example.com',
            role: 'coordinator',
            status: 'active',
          }),
        });
      }
      return Promise.reject(new Error('Unknown url'));
    });
    global.fetch = fetchMock;

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated');
      expect(screen.getByTestId('user-role')).toHaveTextContent('coordinator');
      expect(screen.getByTestId('user-name')).toHaveTextContent('Sarah Coordinator');
    });
  });

  it('clears state on logout', async () => {
    setStoredToken('valid-token');

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({
        id: 'u-1',
        name: 'Sarah Coordinator',
        email: 'coord@example.com',
        role: 'coordinator',
        status: 'active',
      }),
    });

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId('auth-status')).toHaveTextContent('authenticated');
    });

    act(() => {
      screen.getByText('Logout').click();
    });

    expect(screen.getByTestId('auth-status')).toHaveTextContent('unauthenticated');
    expect(screen.getByTestId('user-role')).toHaveTextContent('none');
  });
});
