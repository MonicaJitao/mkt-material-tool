import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { generationApi } from '@/api/generation';
import './page.css';

const PLAN_FIELD_LABELS: Record<string, string> = {
  campaignTheme: '活动主题',
  audienceInsight: '受众洞察',
  visualStyle: '视觉风格',
  cityLogic: '城市逻辑',
  copyTone: '文案语气',
};

export function PlanReviewPage() {
  const navigate = useNavigate();

  const campaignId = sessionStorage.getItem('activeCampaignId') ?? '';
  const rawPlan = sessionStorage.getItem('activePlan');

  const [plan, setPlan] = useState<Record<string, unknown>>(() => {
    try {
      return rawPlan ? (JSON.parse(rawPlan) as Record<string, unknown>) : {};
    } catch {
      return {};
    }
  });
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!campaignId) {
      navigate('/brief');
    }
  }, [campaignId, navigate]);

  const regenerateMutation = useMutation({
    mutationFn: () => generationApi.generatePlan(campaignId),
    onSuccess: (data) => {
      const newPlan = data.structured_plan ?? {};
      setPlan(newPlan);
      sessionStorage.setItem('activePlan', JSON.stringify(newPlan));
      setError(null);
    },
    onError: (err: Error) => {
      setError(err.message ?? '重新生成失败，请重试');
    },
  });

  const approveMutation = useMutation({
    mutationFn: () =>
      generationApi.approvePlan(campaignId, { approved_plan: plan }),
    onSuccess: () => {
      sessionStorage.setItem('approvedPlan', JSON.stringify(plan));
      navigate('/image-batch');
    },
    onError: (err: Error) => {
      setError(err.message ?? '确认方案失败，请重试');
    },
  });

  function handleFieldChange(key: string, value: string) {
    setPlan((prev) => ({ ...prev, [key]: value }));
  }

  function handleLayoutChange(subKey: string, value: string) {
    setPlan((prev) => ({
      ...prev,
      layoutRules: {
        ...(typeof prev.layoutRules === 'object' && prev.layoutRules !== null
          ? (prev.layoutRules as Record<string, unknown>)
          : {}),
        [subKey]: value,
      },
    }));
  }

  const layoutRules =
    typeof plan.layoutRules === 'object' && plan.layoutRules !== null
      ? (plan.layoutRules as Record<string, string>)
      : {};

  const isPending = regenerateMutation.isPending || approveMutation.isPending;

  return (
    <section className="stage-page">
      <header className="stage-page__hero">
        <h2>方案确认</h2>
        <p>审阅 AI 整理的结构化视觉方案，可直接编辑字段，确认后进入底图生成。</p>
      </header>

      <div className="plan-review">
        <div className="plan-review__fields">
          {Object.entries(PLAN_FIELD_LABELS).map(([key, label]) => (
            <label key={key} className="brief-form__label">
              {label}
              <input
                className="brief-form__input"
                type="text"
                value={typeof plan[key] === 'string' ? (plan[key] as string) : ''}
                onChange={(e) => handleFieldChange(key, e.target.value)}
              />
            </label>
          ))}
        </div>

        {Object.keys(layoutRules).length > 0 && (
          <div className="plan-review__layout">
            <p className="plan-review__section-title">版式规则</p>
            <div className="plan-review__fields">
              {Object.entries(layoutRules).map(([subKey, val]) => (
                <label key={subKey} className="brief-form__label">
                  {subKey}
                  <input
                    className="brief-form__input"
                    type="text"
                    value={val ?? ''}
                    onChange={(e) => handleLayoutChange(subKey, e.target.value)}
                  />
                </label>
              ))}
            </div>
          </div>
        )}

        {Object.keys(plan).length === 0 && (
          <p className="brief-form__hint">暂无方案数据，请返回 Brief 页重新生成。</p>
        )}

        {error && <p className="brief-form__error">{error}</p>}

        <div className="brief-form__actions">
          <button
            type="button"
            className="btn btn--ghost"
            disabled={isPending}
            onClick={() => regenerateMutation.mutate()}
          >
            {regenerateMutation.isPending ? '重新生成中…' : '重新生成方案'}
          </button>
          <button
            type="button"
            className="btn btn--primary"
            disabled={isPending || Object.keys(plan).length === 0}
            onClick={() => approveMutation.mutate()}
          >
            {approveMutation.isPending ? '确认中…' : '确认方案，进入底图生成'}
          </button>
        </div>
      </div>
    </section>
  );
}
