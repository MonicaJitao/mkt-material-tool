import type { ImageBatchItem } from '@/api/types';
import { CandidateCard } from './CandidateCard';
import './candidate-grid.css';

interface CandidateGridProps {
  items: ImageBatchItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function CandidateGrid({ items, selectedId, onSelect }: CandidateGridProps) {
  return (
    <div className="candidate-grid" role="list" aria-label="底图候选">
      {items.map((item) => (
        <div key={item.image_asset_id} role="listitem">
          <CandidateCard
            item={item}
            selected={selectedId === item.image_asset_id}
            onSelect={onSelect}
          />
        </div>
      ))}
    </div>
  );
}
