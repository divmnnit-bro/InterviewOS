import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { User, UserRole } from '@/types/api';
import { apiClient, getStoredToken, setStoredToken, clearSession } from '@/api/client';

interface AuthContextType {
  user: User | null;
  role: UserRole | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (data: {
    name: string;
    email: string;
    password: string;
    roll_number?: string;
    branch?: string;
  }) => Promise<User>;
  logout: () => void;
  refreshUser: () => Promise<User | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(getStoredToken());
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchCurrentUser = useCallback(async (): Promise<User | null> => {
    try {
      const me = await apiClient<User>('/auth/me');
      setUser(me);
      return me;
    } catch {
      clearSession();
      setUser(null);
      setToken(null);
      return null;
    }
  }, []);

  useEffect(() => {
    const initAuth = async () => {
      const stored = getStoredToken();
      if (stored) {
        await fetchCurrentUser();
      }
      setIsLoading(false);
    };

    initAuth();
  }, [fetchCurrentUser]);

  const login = async (email: string, password: string): Promise<User> => {
    const res = await apiClient<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });

    setStoredToken(res.access_token);
    setToken(res.access_token);

    const currentUser = await apiClient<User>('/auth/me');
    setUser(currentUser);
    return currentUser;
  };

  const register = async (data: {
    name: string;
    email: string;
    password: string;
    roll_number?: string;
    branch?: string;
  }): Promise<User> => {
    const createdUser = await apiClient<User>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
      isPublic: true,
    });
    return createdUser;
  };

  const logout = () => {
    clearSession();
    setUser(null);
    setToken(null);
  };

  const refreshUser = async () => {
    return await fetchCurrentUser();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        role: user?.role || null,
        token,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
