import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { generationApi } from '@/api/generation';
import { useWorkflowStore } from '@/store/workflowStore';
import './page.css';

const MODEL_OPTIONS = [
  { value: 'claude-sonnet-4-6', label: 'Claude Sonnet 4.6（推荐）' },
  { value: 'claude-opus-4-7', label: 'Claude Opus 4.7（更强）' },
  { value: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash（快速）' },
  { value: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro（更强）' },
];

function hasPlan(obj: Record<string, unknown> | null | undefined): boolean {
  return !!obj && Object.keys(obj).length > 0;
}

export function HtmlGeneratePage() {
  const navigate = useNavigate();

  const campaignId = useWorkflowStore((s) => s.campaignId) ?? '';
  const selectedImageId = useWorkflowStore((s) => s.selectedImageId) ?? '';
  const approvedPlan = useWorkflowStore((s) => s.approvedPlan);
  const htmlModel = useWorkflowStore((s) => s.htmlModel);
  const setHtmlModel = useWorkflowStore((s) => s.setHtmlModel);
  const setHtmlResult = useWorkflowStore((s) => s.setHtmlResult);

  const [error, setError] = useState<string | null>(null);

  const plan: Record<string, unknown> = approvedPlan && hasPlan(approvedPlan) ? approvedPlan : {};

  useEffect(() => {
    if (!campaignId) navigate('/brief');
    else if (!hasPlan(approvedPlan)) navigate('/plan-review');
    else if (!selectedImageId) navigate('/image-batch');
  }, [campaignId, selectedImageId, approvedPlan, navigate]);

  const generateMutation = useMutation({
    mutationFn: () =>
      generationApi.generateHtml(campaignId, {
        selected_image_id: selectedImageId,
        model: htmlModel,
      }),
    onSuccess: (data) => {
      setHtmlResult({ posterId: data.poster_id, versionId: data.version_id });
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
            value={htmlModel}
            onChange={(e) => setHtmlModel(e.target.value)}
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
