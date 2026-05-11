import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { generationApi } from '@/api/generation';
import { assetsApi } from '@/api/assets';
import { CandidateGrid } from '@/components/CandidateGrid/CandidateGrid';
import type { ImageBatchItem } from '@/api/types';
import { useWorkflowStore } from '@/store/workflowStore';
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

  const campaignId = useWorkflowStore((s) => s.campaignId) ?? '';
  const approvedPlan = useWorkflowStore((s) => s.approvedPlan);
  const generatedImages = useWorkflowStore((s) => s.generatedImages);
  const selectedImageId = useWorkflowStore((s) => s.selectedImageId);
  const imageCount = useWorkflowStore((s) => s.imageCount);
  const imageSize = useWorkflowStore((s) => s.imageSize);
  const imageModel = useWorkflowStore((s) => s.imageModel);

  const setImageSettings = useWorkflowStore((s) => s.setImageSettings);
  const setGeneratedImages = useWorkflowStore((s) => s.setGeneratedImages);
  const setSelectedImageId = useWorkflowStore((s) => s.setSelectedImageId);
  const clearHtmlPipeline = useWorkflowStore((s) => s.clearHtmlPipeline);
  const loadAssets = useWorkflowStore((s) => s.loadAssets);

  const [batchId, setBatchId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);

  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const modelRef = useRef(imageModel);
  const assetsFetchAttempted = useRef<string | null>(null);

  useEffect(() => {
    assetsFetchAttempted.current = null;
  }, [campaignId, approvedPlan]);

  useEffect(() => {
    modelRef.current = imageModel;
  }, [imageModel]);

  useEffect(() => {
    setSelectedId(selectedImageId);
  }, [selectedImageId, campaignId]);

  useEffect(() => {
    if (!campaignId) {
      navigate('/brief');
      return;
    }
    if (!approvedPlan || Object.keys(approvedPlan).length === 0) {
      navigate('/plan-review');
      return;
    }
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [campaignId, approvedPlan, navigate]);

  useEffect(() => {
    if (!campaignId) return;
    if (generatedImages.length > 0) return;
    if (selectedImageId) return;
    if (assetsFetchAttempted.current === campaignId) return;
    assetsFetchAttempted.current = campaignId;

    let cancelled = false;
    assetsApi
      .listCampaignAssets(campaignId)
      .then((data) => {
        if (cancelled || data.items.length === 0) return;
        loadAssets(data.items);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [campaignId, generatedImages.length, selectedImageId, loadAssets]);

  async function pollBatch(id: string) {
    try {
      const data = await generationApi.getImageBatch(id);
      setGeneratedImages(data.items);

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
        count: imageCount,
        size: imageSize,
        model: imageModel,
        reference_asset_ids: [],
      }),
    onSuccess: (data) => {
      if (pollRef.current) clearTimeout(pollRef.current);
      setBatchId(data.batch_id);
      setGeneratedImages(data.items);
      setSelectedId(null);
      setSelectedImageId(null);
      clearHtmlPipeline();
      setError(null);
      setIsPolling(true);
      pollRef.current = setTimeout(
        () => pollBatch(data.batch_id),
        pollInterval(imageModel),
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
      setSelectedImageId(data.selected_image_id);
      clearHtmlPipeline();
      navigate('/html-generate');
    },
    onError: (err: Error) => {
      setError(err.message ?? '选择底图失败，请重试');
    },
  });

  const hasCompleted = generatedImages.some((i) => i.status === 'completed');
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
            value={imageCount}
            onChange={(e) => setImageSettings({ imageCount: Number(e.target.value) })}
            disabled={isPolling}
          >
            {[1, 2, 4, 6, 8].map((n) => (
              <option key={n} value={n}>{n} 张</option>
            ))}
          </select>
        </label>

        <label className="brief-form__label">
          比例
          <select
            className="brief-form__input brief-form__select"
            value={imageSize}
            onChange={(e) => setImageSettings({ imageSize: e.target.value })}
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
            value={imageModel}
            onChange={(e) => setImageSettings({ imageModel: e.target.value })}
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

      {generatedImages.length > 0 && (
        <CandidateGrid
          items={generatedImages}
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
