import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { generationApi } from '@/api/generation';
import { CandidateGrid } from '@/components/CandidateGrid/CandidateGrid';
import type { ImageBatchItem } from '@/api/types';
import './page.css';

const SIZE_OPTIONS = ['9:16', '16:9', '1:1', '4:3'];
const MODEL_OPTIONS = [
  { value: 'gemini-3-pro-image-preview-async', label: 'Gemini 3 Pro Async（标准）' },
  { value: 'gemini-3-pro-image-preview-2k-async', label: 'Gemini 3 Pro 2K（较慢）' },
  { value: 'gemini-3-pro-image-preview-4k-async', label: 'Gemini 3 Pro 4K（极慢）' },
];

function pollInterval(model: string): number {
  if (model.includes('4k')) return 20_000;
  if (model.includes('2k')) return 15_000;
  return 10_000;
}

function isBatchDone(items: ImageBatchItem[]): boolean {
  return items.every((i) => i.status === 'completed' || i.status === 'failed');
}

export function ImageBatchPage() {
  const navigate = useNavigate();

  const campaignId = sessionStorage.getItem('activeCampaignId') ?? '';

  const [count, setCount] = useState(4);
  const [size, setSize] = useState('9:16');
  const [model, setModel] = useState(MODEL_OPTIONS[0].value);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [items, setItems] = useState<ImageBatchItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const batchIdRef = useRef<string | null>(null);
  const modelRef = useRef(model);

  useEffect(() => {
    modelRef.current = model;
  }, [model]);

  useEffect(() => {
    if (!campaignId) navigate('/brief');
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [campaignId, navigate]);

  async function pollBatch(id: string) {
    try {
      const data = await generationApi.getImageBatch(id);
      setItems(data.items);

      if (!isBatchDone(data.items)) {
        pollRef.current = setTimeout(
          () => pollBatch(id),
          pollInterval(modelRef.current),
        );
      } else {
        setIsPolling(false);
      }
    } catch {
      setIsPolling(false);
    }
  }

  const startBatchMutation = useMutation({
    mutationFn: () =>
      generationApi.createImageBatch(campaignId, {
        count,
        size,
        model,
        reference_asset_ids: [],
      }),
    onSuccess: (data) => {
      if (pollRef.current) clearTimeout(pollRef.current);
      setBatchId(data.batch_id);
      batchIdRef.current = data.batch_id;
      setItems(data.items);
      setSelectedId(null);
      setError(null);
      setIsPolling(true);
      pollRef.current = setTimeout(
        () => pollBatch(data.batch_id),
        pollInterval(model),
      );
    },
    onError: (err: Error) => {
      setError(err.message ?? '批次创建失败，请重试');
    },
  });

  const selectMutation = useMutation({
    mutationFn: (imageAssetId: string) =>
      generationApi.selectImage(campaignId, { image_asset_id: imageAssetId }),
    onSuccess: (data) => {
      sessionStorage.setItem('selectedImageId', data.selected_image_id);
      navigate('/html-generate');
    },
    onError: (err: Error) => {
      setError(err.message ?? '选择底图失败，请重试');
    },
  });

  const hasCompleted = items.some((i) => i.status === 'completed');
  const canProceed = selectedId !== null && !selectMutation.isPending;

  return (
    <section className="stage-page">
      <header className="stage-page__hero">
        <h2>底图批次生成</h2>
        <p>并发生成多张底图候选，选择满意的一张作为 HTML 海报底图。</p>
      </header>

      <div className="batch-controls">
        <label className="brief-form__label">
          生成数量
          <select
            className="brief-form__input brief-form__select"
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            disabled={isPolling}
          >
            {[2, 4, 6, 8].map((n) => (
              <option key={n} value={n}>{n} 张</option>
            ))}
          </select>
        </label>

        <label className="brief-form__label">
          比例
          <select
            className="brief-form__input brief-form__select"
            value={size}
            onChange={(e) => setSize(e.target.value)}
            disabled={isPolling}
          >
            {SIZE_OPTIONS.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>

        <label className="brief-form__label">
          模型
          <select
            className="brief-form__input brief-form__select"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={isPolling}
          >
            {MODEL_OPTIONS.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </label>

        <div className="batch-controls__actions">
          <button
            type="button"
            className="btn btn--ghost"
            disabled={isPolling || startBatchMutation.isPending}
            onClick={() => startBatchMutation.mutate()}
          >
            {startBatchMutation.isPending
              ? '提交中…'
              : batchId
              ? '重新生成一批'
              : '开始生成'}
          </button>
        </div>
      </div>

      {error && <p className="brief-form__error">{error}</p>}

      {isPolling && (
        <p className="batch-status-hint">
          正在生成中，每 {pollInterval(modelRef.current) / 1000} 秒刷新一次进度…
        </p>
      )}

      {items.length > 0 && (
        <CandidateGrid
          items={items}
          selectedId={selectedId}
          onSelect={(id) => setSelectedId(id)}
        />
      )}

      {hasCompleted && (
        <div className="brief-form__actions">
          <button
            type="button"
            className="btn btn--primary"
            disabled={!canProceed}
            onClick={() => {
              if (selectedId) selectMutation.mutate(selectedId);
            }}
          >
            {selectMutation.isPending
              ? '确认中…'
              : selectedId
              ? '以此底图生成 HTML'
              : '请先选择一张底图'}
          </button>
        </div>
      )}
    </section>
  );
}
