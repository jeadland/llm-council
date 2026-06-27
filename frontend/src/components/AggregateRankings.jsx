import { formatModelLabel } from '../modelUtils';
import './Stage2.css';

// Shared aggregate ranking bar list, reused by Stage 2 and the Winner banner.
export default function AggregateRankings({ aggregateRankings }) {
  if (!aggregateRankings || aggregateRankings.length === 0) return null;

  const worst = Math.max(...aggregateRankings.map((a) => a.average_rank));
  const best = Math.min(...aggregateRankings.map((a) => a.average_rank));
  const range = worst - best || 1;

  return (
    <div className="aggregate-list">
      {aggregateRankings.map((agg, index) => {
        const pct = ((worst - agg.average_rank) / range) * 100;
        return (
          <div key={agg.model || index} className={`aggregate-item ${index < 3 ? 'top-three' : ''}`}>
            <span className="rank-medal" aria-label={`Rank ${index + 1}`}>
              <span className="rank-num">#{index + 1}</span>
            </span>
            <div className="rank-info">
              <div className="rank-model-row">
                <span className="rank-model">{formatModelLabel(agg.model)}</span>
                <span className="rank-score-badge">{agg.average_rank.toFixed(2)}</span>
              </div>
              <div className="rank-bar-track">
                <div
                  className={`rank-bar-fill rank-bar-${index < 3 ? index : 'rest'}`}
                  style={{ width: `${Math.max(pct, 6)}%` }}
                />
              </div>
              <span className="rank-count">
                {agg.rankings_count} vote{agg.rankings_count !== 1 ? 's' : ''}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
