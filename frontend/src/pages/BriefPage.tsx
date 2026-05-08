import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { generationApi } from '@/api/generation';
import type { TemplateListItem } from '@/api/types';
import './page.css';

const SIZE_OPTIONS = ['9:16', '16:9', '1:1', '4:3'];

const DEFAULT_BRIEF: Record<string, string> = {
  festival: '',
  audience: '',
  theme_hint: '',
  cities: '',
  manager_name: '',
  company_name: '',
  visual_style: '',
  size: '9:16',
};

const BRIEF_LABELS: Record<string, string> = {
  festival: '节日 / 营销节点',
  audience: '目标客群',
  theme_hint: '主题方向',
  cities: '城市（逗号分隔）',
  manager_name: '客户经理姓名',
  company_name: '公司名称',
  visual_style: '视觉风格',
  size: '海报尺寸',
};

export function BriefPage() {
  const navigate = useNavigate();

  const [projectName, setProjectName] = useState('');
  const [campaignName, setCampaignName] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateListItem | null>(null);
  const [brief, setBrief] = useState<Record<string, string>>(DEFAULT_BRIEF);
  const [error, setError] = useState<string | null>(null);

  const { data: templateData, isLoading: templatesLoading } = useQuery({
    queryKey: ['templates'],
    queryFn: () => generationApi.listTemplates(),
  });

  const createAndPlanMutation = useMutation({
    mutationFn: async () => {
      setError(null);
      const cities = brief.cities
        ? brief.cities.split(',').map((c) => c.trim()).filter(Boolean)
        : [];

      const briefPayload: Record<string, unknown> = { ...brief, cities };

      const created = await generationApi.createCampaign({
        project_name: projectName.trim(),
        campaign_name: campaignName.trim(),
        template_id: selectedTemplate?.id ?? null,
        brief: briefPayload,
      });

      const planned = await generationApi.generatePlan(created.campaign_id);
      return { campaignId: created.campaign_id, plan: planned };
    },
    onSuccess: ({ campaignId, plan }) => {
      sessionStorage.setItem('activeCampaignId', campaignId);
      sessionStorage.setItem('activePlan', JSON.stringify(plan.structured_plan));
      navigate('/plan-review');
    },
    onError: (err: Error) => {
      setError(err.message ?? '创建活动失败，请重试');
    },
  });

  function handleBriefChange(key: string, value: string) {
    setBrief((prev) => ({ ...prev, [key]: value }));
  }

  const canSubmit =
    projectName.trim().length > 0 &&
    campaignName.trim().length > 0 &&
    !createAndPlanMutation.isPending;

  return (
    <section className="stage-page">
      <header className="stage-page__hero">
        <h2>Brief 录入</h2>
        <p>填写营销活动基本信息，系统将自动整理为结构化视觉方案供你确认。</p>
      </header>

      <div className="brief-form">
        <fieldset className="brief-form__section">
          <legend className="brief-form__legend">项目与活动</legend>
          <div className="brief-form__row">
            <label className="brief-form__label">
              项目名称 <span className="brief-form__required">*</span>
              <input
                className="brief-form__input"
                type="text"
                placeholder="例：微众银行节日营销"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
              />
            </label>
            <label className="brief-form__label">
              活动名称 <span className="brief-form__required">*</span>
              <input
                className="brief-form__input"
                type="text"
                placeholder="例：五一劳动节造城者"
                value={campaignName}
                onChange={(e) => setCampaignName(e.target.value)}
              />
            </label>
          </div>
        </fieldset>

        <fieldset className="brief-form__section">
          <legend className="brief-form__legend">海报模板</legend>
          {templatesLoading ? (
            <p className="brief-form__hint">加载模板中…</p>
          ) : (
            <div className="brief-form__template-grid">
              {(templateData?.items ?? []).map((tpl) => (
                <button
                  key={tpl.id}
                  type="button"
                  className={`brief-form__template-card${selectedTemplate?.id === tpl.id ? ' brief-form__template-card--active' : ''}`}
                  onClick={() => {
                    setSelectedTemplate(tpl);
                    handleBriefChange('size', tpl.default_size);
                  }}
                >
                  <strong>{tpl.name}</strong>
                  {tpl.description && <p>{tpl.description}</p>}
                  <span className="brief-form__template-meta">
                    默认尺寸 {tpl.default_size} · 生成 {tpl.default_image_count} 张
                  </span>
                </button>
              ))}
            </div>
          )}
        </fieldset>

        <fieldset className="brief-form__section">
          <legend className="brief-form__legend">活动信息</legend>
          <div className="brief-form__grid">
            {Object.entries(BRIEF_LABELS).map(([key, label]) => {
              if (key === 'size') {
                return (
                  <label key={key} className="brief-form__label">
                    {label}
                    <select
                      className="brief-form__input brief-form__select"
                      value={brief.size}
                      onChange={(e) => handleBriefChange('size', e.target.value)}
                    >
                      {SIZE_OPTIONS.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </label>
                );
              }
              return (
                <label key={key} className="brief-form__label">
                  {label}
                  <input
                    className="brief-form__input"
                    type="text"
                    placeholder={key === 'cities' ? '深圳, 北京' : ''}
                    value={brief[key] ?? ''}
                    onChange={(e) => handleBriefChange(key, e.target.value)}
                  />
                </label>
              );
            })}
          </div>
        </fieldset>

        {error && <p className="brief-form__error">{error}</p>}

        <div className="brief-form__actions">
          <button
            type="button"
            className="btn btn--primary"
            disabled={!canSubmit}
            onClick={() => createAndPlanMutation.mutate()}
          >
            {createAndPlanMutation.isPending ? '生成中…' : '生成视觉方案'}
          </button>
        </div>
      </div>
    </section>
  );
}
