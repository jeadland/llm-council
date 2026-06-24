import { useState } from 'react';
import './LoginScreen.css';

const OPENROUTER_KEYS_URL = 'https://openrouter.ai/settings/keys';
const OPENROUTER_HOME_URL = 'https://openrouter.ai/';
const OPENROUTER_AUTH_DOCS_URL = 'https://openrouter.ai/docs/api/reference/authentication';

export default function LoginScreen({ onLogin, onSignup, onSignupContinue, onResetPassword }) {
  const [mode, setMode] = useState('login');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [openRouterKey, setOpenRouterKey] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [createdAccount, setCreatedAccount] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const resetFormState = (nextMode) => {
    setMode(nextMode);
    setPassword('');
    setConfirmPassword('');
    setOpenRouterKey('');
    setResetToken('');
    setNewPassword('');
    setCreatedAccount(null);
    setError('');
  };

  const validatePasswordMatch = (value = password, confirmation = confirmPassword) => {
    if (value.length < 12) return 'Password must be at least 12 characters';
    if (value !== confirmation) return 'Passwords do not match';
    return '';
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');

    if (mode === 'signup') {
      const passwordError = validatePasswordMatch();
      if (passwordError) {
        setError(passwordError);
        return;
      }
      if (!openRouterKey.trim()) {
        setError('OpenRouter API key is required');
        return;
      }
    }

    if (mode === 'reset') {
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
      if (mode === 'signup') {
        const result = await onSignup({
          name,
          email,
          password,
          openRouterApiKey: openRouterKey,
        });
        setCreatedAccount(result);
      } else if (mode === 'reset') {
        await onResetPassword(email, resetToken, newPassword);
      } else {
        await onLogin(email, password);
      }
    } catch (e) {
      setError(e.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  if (createdAccount) {
    return (
      <div className="login-screen">
        <section className="login-panel login-panel-confirm" aria-labelledby="account-created-title">
          <img
            src="/images/llm-council-icon.svg"
            alt=""
            className="login-logo"
            width="56"
            height="56"
            onError={(e) => { e.target.style.display = 'none'; }}
          />
          <div className="login-confirm-badge" aria-hidden="true">✓</div>
          <h1 id="account-created-title">Account created</h1>
          <p>Your OpenRouter key is connected. You can start using LLM Council with your own model credits.</p>
          <div className="login-confirm-detail">
            <span>Email</span>
            <strong>{createdAccount.email}</strong>
          </div>
          {createdAccount.openrouter?.masked_key && (
            <div className="login-confirm-detail">
              <span>OpenRouter key</span>
              <strong>{createdAccount.openrouter.masked_key}</strong>
            </div>
          )}
          <button
            className="login-button"
            type="button"
            onClick={() => onSignupContinue(createdAccount)}
          >
            Continue
          </button>
        </section>
      </div>
    );
  }

  const isSignup = mode === 'signup';
  const isReset = mode === 'reset';

  return (
    <div className="login-screen">
      <form className={`login-panel${isSignup ? ' login-panel-wide' : ''}`} onSubmit={handleSubmit}>
        <div className="login-heading-row">
          <img
            src="/images/llm-council-icon.svg"
            alt=""
            className="login-logo"
            width="56"
            height="56"
            onError={(e) => { e.target.style.display = 'none'; }}
          />
          <div>
            <h1>LLM Council</h1>
            <p>
              {isSignup
                ? 'Create an account with your own OpenRouter key.'
                : isReset
                  ? 'Reset the owner password.'
                  : 'Sign in to continue.'}
            </p>
          </div>
        </div>

        <div className="login-mode-tabs" role="tablist" aria-label="Authentication mode">
          <button
            type="button"
            className={mode === 'login' ? 'active' : ''}
            onClick={() => resetFormState('login')}
          >
            Sign in
          </button>
          <button
            type="button"
            className={mode === 'signup' ? 'active' : ''}
            onClick={() => resetFormState('signup')}
          >
            Create account
          </button>
        </div>

        {isSignup && (
          <div className="openrouter-guide">
            <div>
              <strong>Bring your own OpenRouter key</strong>
              <p>LLM Council does not provide model credits in this version.</p>
            </div>
            <ol>
              <li>
                Existing account: open{' '}
                <a href={OPENROUTER_KEYS_URL} target="_blank" rel="noreferrer">OpenRouter API keys</a>.
              </li>
              <li>
                New account: create or sign in at{' '}
                <a href={OPENROUTER_HOME_URL} target="_blank" rel="noreferrer">OpenRouter</a>, then add credits if needed.
              </li>
              <li>Create a key, optionally set a credit limit, copy it, and paste it below.</li>
            </ol>
            <a className="openrouter-guide-link" href={OPENROUTER_AUTH_DOCS_URL} target="_blank" rel="noreferrer">
              OpenRouter API key docs
            </a>
          </div>
        )}

        {isSignup && (
          <label className="login-field">
            <span>Name <em>optional</em></span>
            <input
              type="text"
              autoComplete="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
        )}

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

        {isReset ? (
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
          </>
        ) : (
          <label className="login-field">
            <span>Password</span>
            <input
              type="password"
              autoComplete={isSignup ? 'new-password' : 'current-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
        )}

        {(isSignup || isReset) && (
          <label className="login-field">
            <span>{isReset ? 'Confirm new password' : 'Confirm password'}</span>
            <input
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </label>
        )}

        {isSignup && (
          <label className="login-field">
            <span>OpenRouter API key</span>
            <input
              type="password"
              autoComplete="off"
              value={openRouterKey}
              onChange={(e) => setOpenRouterKey(e.target.value)}
              placeholder="sk-or-v1-..."
              required
            />
          </label>
        )}

        {error && <div className="login-error">{error}</div>}

        <button className="login-button" type="submit" disabled={loading}>
          {loading
            ? isSignup ? 'Creating account...' : isReset ? 'Resetting...' : 'Signing in...'
            : isSignup ? 'Create account' : isReset ? 'Reset password' : 'Sign in'}
        </button>

        <button
          className="login-link-button"
          type="button"
          onClick={() => resetFormState(isReset ? 'login' : 'reset')}
          disabled={loading}
        >
          {isReset ? 'Back to sign in' : 'Owner password reset'}
        </button>
      </form>
    </div>
  );
}
