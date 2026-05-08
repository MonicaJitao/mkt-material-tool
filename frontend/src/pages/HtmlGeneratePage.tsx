import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { generationApi } from '@/api/generation';
import './page.css';

const MODEL_OPTIONS = [
  { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6（推荐）' },
  { value: 'claude-opus-4-7', label: 'Claude Opus 4.7（更强）' },
];

export function HtmlGeneratePage() {
  const navigate = useNavigate();

  const campaignId = sessionStorage.getItem('activeCampaignId') ?? '';
  const selectedImageId = sessionStorage.getItem('selectedImageId') ?? '';
  const rawPlan = sessionStorage.getItem('approvedPlan');

  const [model, setModel] = useState(MODEL_OPTIONS[0].value);
  const [error, setError] = useState<string | null>(null);

  const plan: Record<string, unknown> = (() => {
    try {
      return rawPlan ? (JSON.parse(rawPlan) as Record<string, unknown>) : {};
    } catch {
      return {};
    }
  })();

  useEffect(() => {
    if (!campaignId) navigate('/brief');
    else if (!selectedImageId) navigate('/image-batch');
  }, [campaignId, selectedImageId, navigate]);

  const generateMutation = useMutation({
    mutationFn: () =>
      generationApi.generateHtml(campaignId, {
        selected_image_id: selectedImageId,
        model,
      }),
    onSuccess: (data) => {
      sessionStorage.setItem('activePosterId', data.poster_id);
      sessionStorage.setItem('activeVersionId', data.version_id);
      navigate('/html-editor');
    },
    onError: (err: Error) => {
      setError(err.message ?? 'HTML 生成失败，请重试');
    },
  });

  const planEntries = Object.entries(plan).filter(
    ([k]) => k !== 'layoutRules',
  );

  return (
    <section className="stage-page">
      <header className="stage-page__hero">
        <h2>HTML 生成</h2>
        <p>基于选中底图和确认方案，调用 Claude 生成单文件 HTML 海报。</p>
      </header>

      <div className="html-generate">
        <div className="html-generate__preview-row">
          <div className="html-generate__image-preview">
            <p className="html-generate__section-label">选中底图</p>
            {selectedImageId ? (
              <img
                className="html-generate__thumb"
                src={`/api/assets/${selectedImageId}/file`}
                alt="选中底图"
              />
            ) : (
              <div className="html-generate__no-image">未选择底图</div>
            )}
          </div>

          <div className="html-generate__plan-summary">
            <p className="html-generate__section-label">视觉方案摘要</p>
            {planEntries.length > 0 ? (
              <dl className="html-generate__plan-dl">
                {planEntries.map(([k, v]) => (
                  <div key={k} className="html-generate__plan-row">
                    <dt>{k}</dt>
                    <dd>{typeof v === 'string' ? v : JSON.stringify(v)}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="brief-form__hint">无方案数据</p>
            )}
          </div>
        </div>

        <label className="brief-form__label html-generate__model-select">
          生成模型
          <select
            className="brief-form__input brief-form__select"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={generateMutation.isPending}
          >
            {MODEL_OPTIONS.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </label>

        {error && <p className="brief-form__error">{error}</p>}

        <div className="brief-form__actions">
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => navigate('/image-batch')}
            disabled={generateMutation.isPending}
          >
            返回重选底图
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={!selectedImageId || generateMutation.isPending}
            onClick={() => generateMutation.mutate()}
          >
            {generateMutation.isPending ? '生成中，请稍候…' : '生成 HTML 海报'}
          </button>
        </div>
      </div>
    </section>
  );
}
