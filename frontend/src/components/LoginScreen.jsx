import { useState } from 'react';
import './LoginScreen.css';

export default function LoginScreen({ onLogin, onResetPassword }) {
  const [email, setEmail] = useState('josh.adland@gmail.com');
  const [password, setPassword] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [resetMode, setResetMode] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    if (resetMode) {
      if (newPassword !== confirmPassword) {
        setError('New passwords do not match');
        return;
      }
      if (newPassword.length < 12) {
        setError('New password must be at least 12 characters');
        return;
      }
    }
    setLoading(true);
    try {
      if (resetMode) {
        await onResetPassword(email, resetToken, newPassword);
      } else {
        await onLogin(email, password);
      }
    } catch (e) {
      setError(e.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const toggleResetMode = () => {
    setError('');
    setPassword('');
    setResetToken('');
    setNewPassword('');
    setConfirmPassword('');
    setResetMode((value) => !value);
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
        <p>{resetMode ? 'Reset your owner password.' : 'Sign in to continue.'}</p>

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

        {resetMode ? (
          <>
            <label className="login-field">
              <span>Recovery code</span>
              <input
                type="password"
                autoComplete="one-time-code"
                value={resetToken}
                onChange={(e) => setResetToken(e.target.value)}
                required
              />
            </label>

            <label className="login-field">
              <span>New password</span>
              <input
                type="password"
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
            </label>

            <label className="login-field">
              <span>Confirm new password</span>
              <input
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />
            </label>
          </>
        ) : (
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
        )}

        {error && <div className="login-error">{error}</div>}

        <button className="login-button" type="submit" disabled={loading}>
          {loading ? (resetMode ? 'Resetting...' : 'Signing in...') : (resetMode ? 'Reset password' : 'Sign in')}
        </button>
        <button className="login-link-button" type="button" onClick={toggleResetMode} disabled={loading}>
          {resetMode ? 'Back to sign in' : 'Reset password'}
        </button>
      </form>
    </div>
  );
}
