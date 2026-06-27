import { useState } from 'react';
import { ChevronDown, Crown } from 'lucide-react';
import AggregateRankings from './AggregateRankings';
import { formatModelLabel, providerMeta } from '../modelUtils';
import './WinnerBanner.css';

export default function WinnerBanner({ aggregateRankings, voteLabel }) {
  const [open, setOpen] = useState(false);

  if (!aggregateRankings || aggregateRankings.length === 0) return null;

  const winner = aggregateRankings[0];
  const meta = providerMeta(winner.model);
  const score = typeof winner.average_rank === 'number' ? winner.average_rank.toFixed(2) : null;
  const hasMore = aggregateRankings.length > 1;

  return (
    <div className="winner-banner">
      <button
        type="button"
        className="winner-banner-head"
        onClick={() => hasMore && setOpen((v) => !v)}
        aria-expanded={hasMore ? open : undefined}
        disabled={!hasMore}
      >
        <span className="winner-avatar" style={{ '--agent-color': meta.color }} aria-hidden="true">
          {meta.glyph}
          <span className="winner-avatar-crown" aria-hidden="true">
            <Crown size={11} />
          </span>
        </span>

        <span className="winner-info">
          <span className="winner-eyebrow">Council winner</span>
          <span className="winner-name">{formatModelLabel(winner.model)}</span>
        </span>

        <span className="winner-meta">
          {score && <span className="winner-score">{score} avg</span>}
          {voteLabel && <span className="winner-votes">{voteLabel}</span>}
        </span>

        {hasMore && (
          <ChevronDown
            size={18}
            className={`winner-chevron${open ? ' winner-chevron--open' : ''}`}
            aria-hidden="true"
          />
        )}
      </button>

      {open && hasMore && (
        <div className="winner-scoreboard">
          <AggregateRankings aggregateRankings={aggregateRankings} />
        </div>
      )}
    </div>
  );
}
