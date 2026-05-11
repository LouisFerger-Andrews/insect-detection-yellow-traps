import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';

type AdminOverview = {
  totals: {
    users: number;
    uploads: number;
    detections: number;
  };
  users: Array<{
    id: number;
    email: string;
    full_name: string;
    role: string;
    created_at: string;
  }>;
  uploads: Array<{
    id: number;
    user_id: number;
    field_id: string;
    trap_id?: string | null;
    trap_code: string;
    capture_date: string;
    detection_count: number;
    confidence_avg: number;
    created_at: string;
  }>;
};

export default function AdminPage() {
  const { token } = useAuth();
  const [data, setData] = useState<AdminOverview | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const load = async () => {
      if (!token) return;
      try {
        const response = await apiClient.get<AdminOverview>('/api/admin/overview', token);
        setData(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load admin data');
      }
    };
    void load();
  }, [token]);

  if (error) {
    return <div className="card error">{error}</div>;
  }

  if (!data) {
    return <div className="card">Loading admin data...</div>;
  }

  return (
    <section className="card">
      <h2>Admin Overview</h2>
      <p>
        Users: {data.totals.users} | Uploads: {data.totals.uploads} | Detections: {data.totals.detections}
      </p>

      <h3>Users</h3>
      <ul className="list">
        {data.users.map((user) => (
          <li key={user.id}>
            #{user.id} {user.email} ({user.role})
          </li>
        ))}
      </ul>

      <h3>Recent Uploads</h3>
      <ul className="list">
        {data.uploads.map((upload) => (
          <li key={upload.id}>
            #{upload.id} user={upload.user_id} field={upload.field_id} trap={upload.trap_code} trapId=
            {upload.trap_id ?? '-'} detections=
            {upload.detection_count}
          </li>
        ))}
      </ul>
    </section>
  );
}
