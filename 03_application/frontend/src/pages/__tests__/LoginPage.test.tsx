import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '../LoginPage';

const useAuthMock = vi.fn();
const navigateMock = vi.fn();

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

describe('LoginPage', () => {
  beforeEach(() => {
    useAuthMock.mockReset();
    navigateMock.mockReset();
  });

  it('redirects immediately when token exists', () => {
    useAuthMock.mockReturnValue({ token: 'abc', login: vi.fn(), register: vi.fn() });
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );
    expect(screen.queryByText('Log In')).not.toBeInTheDocument();
  });

  it('logs in and navigates to dashboard', async () => {
    const login = vi.fn().mockResolvedValue(undefined);
    useAuthMock.mockReturnValue({ token: null, login, register: vi.fn() });
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'u@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Log In' }));

    await waitFor(() => expect(login).toHaveBeenCalledWith('u@example.com', 'password123'));
    expect(navigateMock).toHaveBeenCalledWith('/');
  });

  it('switches to register mode and shows error when register fails', async () => {
    const register = vi.fn().mockRejectedValue(new Error('bad register'));
    useAuthMock.mockReturnValue({ token: null, login: vi.fn(), register });
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    fireEvent.click(screen.getByRole('button', { name: 'No account? Register' }));
    fireEvent.change(screen.getByLabelText('Full Name'), { target: { value: 'User Name' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'n@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'password123' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create Account' }));

    await waitFor(() => expect(register).toHaveBeenCalled());
    expect(screen.getByText('bad register')).toBeInTheDocument();
  });
});

