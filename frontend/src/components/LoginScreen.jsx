import { useEffect, useState } from "react";
import "./LoginScreen.css";

export default function LoginScreen({ onGoogleLogin }) {
  const [error] = useState(() => getAuthErrorFromUrl());
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    if (!params.has("auth_error")) return;
    params.delete("auth_error");
    const nextSearch = params.toString();
    const nextUrl = `${window.location.pathname}${nextSearch ? `?${nextSearch}` : ""}${window.location.hash}`;
    window.history.replaceState({}, "", nextUrl);
  }, []);

  const handleGoogleLogin = () => {
    setLoading(true);
    onGoogleLogin();
  };

  return (
    <div className="login-screen">
      <section
        className="login-panel"
        aria-labelledby="llm-council-login-title"
      >
        <div className="login-heading-row">
          <img
            src={`${import.meta.env.BASE_URL}images/llm-council-icon.svg`}
            alt=""
            className="login-logo"
            width="56"
            height="56"
            onError={(e) => {
              e.target.style.display = "none";
            }}
          />
          <div>
            <h1 id="llm-council-login-title">LLM Council</h1>
            <p>Sign in with Google to open your private council workspace.</p>
          </div>
        </div>

        <button
          className="login-button login-google-button"
          type="button"
          onClick={handleGoogleLogin}
          disabled={loading}
        >
          <GoogleLogo />
          {loading ? "Opening Google..." : "Continue with Google"}
        </button>

        {error && <div className="login-error">{error}</div>}
        <p className="login-privacy-note">
          No password. Google verifies your email; conversations stay scoped to
          your account.
        </p>
      </section>
    </div>
  );
}

function getAuthErrorFromUrl() {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("auth_error") || "";
}

function GoogleLogo() {
  return (
    <svg aria-hidden="true" viewBox="0 0 18 18" className="google-logo">
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.71v2.25h2.92c1.7-1.57 2.68-3.88 2.68-6.6z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.2l-2.92-2.25c-.8.54-1.84.86-3.04.86-2.34 0-4.33-1.58-5.04-3.71H.96v2.32A9 9 0 0 0 9 18z"
      />
      <path
        fill="#FBBC05"
        d="M3.96 10.7a5.41 5.41 0 0 1 0-3.4V4.98H.96a9 9 0 0 0 0 8.04l3-2.32z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.43 1.35l2.59-2.59A8.63 8.63 0 0 0 9 0 9 9 0 0 0 .96 4.98l3 2.32C4.67 5.16 6.66 3.58 9 3.58z"
      />
    </svg>
  );
}
