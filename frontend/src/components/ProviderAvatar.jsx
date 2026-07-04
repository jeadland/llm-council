import { useState } from 'react';
import { hasProviderLogo, providerLogoSrc, providerMeta } from '../modelUtils';
import './ProviderAvatar.css';

function ProviderAvatarMark({ modelId, provider }) {
  const meta = modelId ? providerMeta(modelId) : providerMeta(provider ? `${provider}/model` : '');
  const resolvedProvider = provider || meta.provider;
  const logoSrc = providerLogoSrc(resolvedProvider);
  const showLogo = Boolean(logoSrc) && hasProviderLogo(resolvedProvider);
  const [logoFailed, setLogoFailed] = useState(false);

  if (showLogo && !logoFailed) {
    return (
      <img
        src={logoSrc}
        alt=""
        className="provider-avatar-logo"
        loading="lazy"
        decoding="async"
        onError={() => setLogoFailed(true)}
      />
    );
  }

  return meta.glyph;
}

export default function ProviderAvatar({
  modelId,
  provider,
  className = '',
  title,
  children,
  ...props
}) {
  const meta = modelId ? providerMeta(modelId) : providerMeta(provider ? `${provider}/model` : '');
  const resolvedProvider = provider || meta.provider;
  const logoSrc = providerLogoSrc(resolvedProvider);
  const showLogo = Boolean(logoSrc) && hasProviderLogo(resolvedProvider);

  const classes = [
    'provider-avatar',
    showLogo ? 'provider-avatar--logo' : '',
    className,
  ].filter(Boolean).join(' ');

  return (
    <span
      className={classes}
      style={{ '--provider-color': meta.color, '--agent-color': meta.color }}
      title={title || meta.label}
      {...props}
    >
      <ProviderAvatarMark
        key={resolvedProvider}
        modelId={modelId}
        provider={provider}
      />
      {children}
    </span>
  );
}
