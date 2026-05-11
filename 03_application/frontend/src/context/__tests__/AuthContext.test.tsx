import { act, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { AuthProvider, useAuth } from '../AuthContext';

const getMock = vi.fn();
const postMock = vi.fn();

vi.mock('../../api/client', () => ({
  apiClient: {
    get: (...args: unknown[]) => getMock(...args),
    post: (...args: unknown[]) => postMock(...args),
  },
}));

function Probe() {
  const auth = useAuth();
  return (
    <>
      <div data-testid="token">{auth.token ?? 'none'}</div>
      <div data-testid="user">{auth.user?.email ?? 'none'}</div>
      <button onClick={() => auth.login('u@example.com', 'password123')}>login</button>
      <button onClick={() => auth.register('n@example.com', 'New User', 'password123')}>register</button>
      <button onClick={() => auth.logout()}>logout</button>
      <button onClick={() => void auth.refreshUser()}>refresh</button>
    </>
  );
}

describe('AuthProvider', () => {
  beforeEach(() => {
    localStorage.clear();
    getMock.mockReset();
    postMock.mockReset();
  });

  it('loads user from token and can logout', async () => {
    localStorage.setItem('auth_token', 'abc');
    getMock.mockResolvedValue({ email: 'u@example.com' });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByTestId('user').textContent).toBe('u@example.com'));

    await act(async () => {
      screen.getByText('logout').click();
    });
    expect(localStorage.getItem('auth_token')).toBeNull();
    expect(screen.getByTestId('token').textContent).toBe('none');
  });

  it('clears invalid token when refresh fails', async () => {
    localStorage.setItem('auth_token', 'abc');
    getMock.mockRejectedValue(new Error('unauthorized'));

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await waitFor(() => expect(localStorage.getItem('auth_token')).toBeNull());
  });

  it('login stores token and register chains login', async () => {
    postMock
      .mockResolvedValueOnce({ access_token: 'token-login' })
      .mockResolvedValueOnce({ ok: true })
      .mockResolvedValueOnce({ access_token: 'token-register' });
    getMock.mockResolvedValue({ email: 'n@example.com' });

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );

    await act(async () => {
      screen.getByText('login').click();
    });
    expect(localStorage.getItem('auth_token')).toBe('token-login');

    await act(async () => {
      screen.getByText('register').click();
    });
    expect(localStorage.getItem('auth_token')).toBe('token-register');
  });
});
