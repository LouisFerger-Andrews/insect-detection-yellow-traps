import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { apiClient } from '../api/client';
import type { UserProfile } from '../types/api';

type AuthContextType = {
  token: string | null;
  user: UserProfile | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, fullName: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(localStorage.getItem('auth_token'));
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = async () => {
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      const profile = await apiClient.get<UserProfile>('/api/auth/me', token);
      setUser(profile);
    } catch {
      setToken(null);
      setUser(null);
      localStorage.removeItem('auth_token');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void refreshUser();
  }, [token]);

  const login = async (email: string, password: string) => {
    const tokenResponse = await apiClient.post<{ access_token: string }>('/api/auth/login', {
      email,
      password,
    });
    localStorage.setItem('auth_token', tokenResponse.access_token);
    setToken(tokenResponse.access_token);
  };

  const register = async (email: string, fullName: string, password: string) => {
    await apiClient.post('/api/auth/register', {
      email,
      full_name: fullName,
      password,
    });
    await login(email, password);
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    setToken(null);
    setUser(null);
  };

  const value = useMemo(
    () => ({ token, user, isLoading, login, register, logout, refreshUser }),
    [token, user, isLoading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}
