import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { token, login, register } = useAuth();
  const navigate = useNavigate();

  const [isRegisterMode, setIsRegisterMode] = useState(false);
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (token) {
    return <Navigate to="/" replace />;
  }

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    setBusy(true);

    try {
      if (isRegisterMode) {
        await register(email, fullName, password);
      } else {
        await login(email, password);
      }
      navigate('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page auth-page">
      <div className="card auth-card">
        <h1>Spotted Wing Drosophila Monitoring Platform</h1>
        <p>Sign in to manage fields, upload trap images, and analyze insect detections.</p>

        <form onSubmit={onSubmit} className="form">
          {isRegisterMode ? (
            <label>
              Full Name
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} required minLength={2} />
            </label>
          ) : null}

          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>

          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
            />
          </label>

          {error ? <div className="error">{error}</div> : null}

          <button type="submit" disabled={busy}>
            {busy ? 'Please wait...' : isRegisterMode ? 'Create Account' : 'Log In'}
          </button>
        </form>

        <button className="link-btn" onClick={() => setIsRegisterMode((v) => !v)}>
          {isRegisterMode ? 'Have an account? Log in' : 'No account? Register'}
        </button>
      </div>
    </div>
  );
}
