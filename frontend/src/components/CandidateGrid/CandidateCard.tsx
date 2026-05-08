import type { ImageBatchItem } from '@/api/types';
import './candidate-grid.css';

interface CandidateCardProps {
  item: ImageBatchItem;
  selected: boolean;
  onSelect: (id: string) => void;
}

export function CandidateCard({ item, selected, onSelect }: CandidateCardProps) {
  const isCompleted = item.status === 'completed';
  const isFailed = item.status === 'failed';
  const isLoading = !isCompleted && !isFailed;

  return (
    <article
      className={[
        'candidate-card',
        selected ? 'candidate-card--selected' : '',
        isFailed ? 'candidate-card--failed' : '',
        isLoading ? 'candidate-card--loading' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      aria-selected={selected}
    >
      <div className="candidate-card__image-wrap">
        {isLoading && (
          <div className="candidate-card__shimmer" aria-label="生成中">
            <div className="candidate-card__progress-bar">
              <div
                className="candidate-card__progress-fill"
                style={{ width: `${item.progress}%` }}
              />
            </div>
            <span className="candidate-card__progress-label">{item.progress}%</span>
          </div>
        )}

        {isFailed && (
          <div className="candidate-card__error-state">
            <span className="candidate-card__error-icon">✕</span>
            <p className="candidate-card__error-msg">
              {item.error_message ?? '生成失败'}
            </p>
          </div>
        )}

        {isCompleted && item.preview_url && (
          <img
            className="candidate-card__img"
            src={item.preview_url}
            alt="底图候选"
            loading="lazy"
          />
        )}
      </div>

      {isCompleted && (
        <div className="candidate-card__footer">
          <button
            type="button"
            className={`btn ${selected ? 'btn--primary' : 'btn--ghost'} candidate-card__select-btn`}
            onClick={() => onSelect(item.image_asset_id)}
          >
            {selected ? '已选为底图' : '选为底图'}
          </button>
        </div>
      )}
    </article>
  );
}
