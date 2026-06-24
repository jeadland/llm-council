import { useState } from 'react';
import './LoginScreen.css';

export default function LoginScreen({ onLogin }) {
  const [email, setEmail] = useState('josh.adland@gmail.com');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      await onLogin(email, password);
    } catch (e) {
      setError(e.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <form className="login-panel" onSubmit={handleSubmit}>
        <img
          src="/images/llm-council-icon.svg"
          alt=""
          className="login-logo"
          width="56"
          height="56"
          onError={(e) => { e.target.style.display = 'none'; }}
        />
        <h1>LLM Council</h1>
        <p>Sign in to continue.</p>

        <label className="login-field">
          <span>Email</span>
          <input
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>

        <label className="login-field">
          <span>Password</span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        {error && <div className="login-error">{error}</div>}

        <button className="login-button" type="submit" disabled={loading}>
          {loading ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}
