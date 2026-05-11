import { render, screen, waitFor } from '@testing-library/react';
import AdminPage from '../AdminPage';

const useAuthMock = vi.fn();
const getMock = vi.fn();

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => useAuthMock(),
}));

vi.mock('../../api/client', () => ({
  apiClient: {
    get: (...args: unknown[]) => getMock(...args),
  },
}));

describe('AdminPage', () => {
  beforeEach(() => {
    useAuthMock.mockReset();
    getMock.mockReset();
  });

  it('shows loading state first', () => {
    useAuthMock.mockReturnValue({ token: null });
    render(<AdminPage />);
    expect(screen.getByText('Loading admin data...')).toBeInTheDocument();
  });

  it('shows admin overview after fetch', async () => {
    useAuthMock.mockReturnValue({ token: 'token' });
    getMock.mockResolvedValue({
      totals: { users: 2, uploads: 4, detections: 11 },
      users: [{ id: 1, email: 'u@example.com', full_name: 'U', role: 'admin', created_at: '2026-01-01' }],
      uploads: [
        {
          id: 10,
          user_id: 1,
          field_id: 'field-1',
          trap_code: 'R01-P01',
          trap_id: null,
          capture_date: '2026-01-10',
          detection_count: 3,
          confidence_avg: 0.8,
          created_at: '2026-01-10',
        },
      ],
    });

    render(<AdminPage />);

    await waitFor(() => expect(getMock).toHaveBeenCalledWith('/api/admin/overview', 'token'));
    expect(screen.getByText('Admin Overview')).toBeInTheDocument();
    expect(screen.getByText(/Users: 2 \| Uploads: 4 \| Detections: 11/)).toBeInTheDocument();
    expect(screen.getByText(/#10 user=1 field=field-1/)).toBeInTheDocument();
  });

  it('shows error on fetch failure', async () => {
    useAuthMock.mockReturnValue({ token: 'token' });
    getMock.mockRejectedValue(new Error('boom'));

    render(<AdminPage />);

    await waitFor(() => expect(screen.getByText('boom')).toBeInTheDocument());
  });
});

