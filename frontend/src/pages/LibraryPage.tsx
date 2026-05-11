import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { assetsApi } from '@/api/assets';
import type { CampaignOut } from '@/api/types';
import { useWorkflowStore } from '@/store/workflowStore';
import './library-page.css';

/** 活动状态 → 中文标签 */
const STATUS_LABELS: Record<string, string> = {
  draft: '草稿',
  brief_ready: 'Brief 已就绪',
  plan_pending_review: '方案待确认',
  plan_approved: '方案已确认',
  image_generating: '底图生成中',
  image_pending_selection: '底图待选择',
  image_selected: '底图已选择',
  html_generating: 'HTML 生成中',
  html_ready: 'HTML 就绪',
  editing: '编辑中',
  archived: '已归档',
  failed: '失败',
};

/** 活动状态 → 状态色 class */
function statusClass(status: string): string {
  if (status === 'failed') return 'status-badge--error';
  if (status.includes('generating')) return 'status-badge--warning';
  if (['html_ready', 'editing', 'image_selected'].includes(status)) return 'status-badge--success';
  if (['archived'].includes(status)) return 'status-badge--muted';
  return 'status-badge--info';
}

/** 活动状态 → 继续编辑的目标路由 */
function resolveContinuePath(status: string): string {
  if (['draft', 'brief_ready'].includes(status)) return '/brief';
  if (status === 'plan_pending_review') return '/plan-review';
  if (status === 'plan_approved') return '/image-batch';
  if (['image_generating', 'image_pending_selection', 'image_selected'].includes(status)) return '/image-batch';
  if (['html_generating', 'html_ready'].includes(status)) return '/html-generate';
  if (status === 'editing') return '/html-editor';
  // failed / archived — 从 brief 开始或 html-editor 看结果
  if (status === 'failed') return '/brief';
  return '/html-editor';
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

async function hydrateWorkflowFromCampaign(campaign: CampaignOut) {
  const store = useWorkflowStore.getState();
  store.reset();
  store.loadCampaignBase(campaign);

  const [assetsResult, postersResult] = await Promise.allSettled([
    assetsApi.listCampaignAssets(campaign.id),
    assetsApi.listCampaignPosters(campaign.id),
  ]);

  if (assetsResult.status === 'fulfilled') {
    store.loadAssets(assetsResult.value.items);
  }

  if (postersResult.status === 'fulfilled') {
    store.loadPosters(postersResult.value);
  }
}

const ALL_STATUSES = [
  'plan_pending_review',
  'plan_approved',
  'image_generating',
  'image_pending_selection',
  'image_selected',
  'html_generating',
  'html_ready',
  'editing',
  'archived',
  'failed',
];

export function LibraryPage() {
  const navigate = useNavigate();

  // 选中的项目 ID
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  // 状态筛选
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [continuingId, setContinuingId] = useState<string | null>(null);
  const [continueError, setContinueError] = useState<string | null>(null);

  // ── 查询项目列表 ──────────────────────────────────────────────
  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: () => assetsApi.listProjects(),
  });

  // ── 查询选中项目的活动列表 ─────────────────────────────────────
  const campaignsQuery = useQuery({
    queryKey: ['campaigns', selectedProjectId, statusFilter],
    queryFn: () =>
      assetsApi.listCampaigns({
        project_id: selectedProjectId ?? undefined,
        status: statusFilter || undefined,
      }),
    enabled: !!selectedProjectId,
  });

  const handleContinue = useCallback(
    async (campaign: CampaignOut) => {
      setContinuingId(campaign.id);
      setContinueError(null);
      try {
        await hydrateWorkflowFromCampaign(campaign);
        navigate(resolveContinuePath(campaign.status));
      } catch (err) {
        setContinueError(err instanceof Error ? err.message : '恢复活动失败，请重试');
      } finally {
        setContinuingId(null);
      }
    },
    [navigate],
  );

  const projects = projectsQuery.data?.items ?? [];
  const campaigns = campaignsQuery.data?.items ?? [];

  return (
    <section className="library-page">
      <header className="stage-page__hero">
        <h2>素材库</h2>
        <p>按项目和活动查看底图、HTML 与版本历史，选择已有活动继续编辑。</p>
      </header>

      {continueError && <p className="brief-form__error">{continueError}</p>}

      <div className="library-page__layout">
        {/* 左侧：项目列表 */}
        <div className="library-page__projects">
          <div className="library-page__panel-label">项目</div>
          {projectsQuery.isLoading ? (
            <p className="brief-form__hint">加载中…</p>
          ) : projects.length === 0 ? (
            <p className="brief-form__hint">暂无项目。创建第一个活动后将自动创建项目。</p>
          ) : (
            <ul className="library-page__project-list">
              {projects.map((p) => (
                <li
                  key={p.id}
                  className={`library-page__project-item ${
                    p.id === selectedProjectId ? 'library-page__project-item--active' : ''
                  }`}
                  onClick={() => setSelectedProjectId(p.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      setSelectedProjectId(p.id);
                    }
                  }}
                >
                  <span className="library-page__project-name">{p.name}</span>
                  <span className="library-page__project-time">{formatTime(p.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* 右侧：活动列表 */}
        <div className="library-page__campaigns">
          <div className="library-page__campaigns-header">
            <span className="library-page__panel-label">活动</span>
            <select
              className="brief-form__input brief-form__select library-page__status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">全部状态</option>
              {ALL_STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABELS[s] ?? s}
                </option>
              ))}
            </select>
          </div>

          {!selectedProjectId ? (
            <p className="brief-form__hint">请先选择左侧项目</p>
          ) : campaignsQuery.isLoading ? (
            <p className="brief-form__hint">加载中…</p>
          ) : campaigns.length === 0 ? (
            <p className="brief-form__hint">
              {statusFilter ? '当前筛选下无活动' : '该项目下暂无活动'}
            </p>
          ) : (
            <div className="library-page__campaign-grid">
              {campaigns.map((c) => (
                <article key={c.id} className="library-page__campaign-card">
                  <div className="library-page__campaign-top">
                    <h4 className="library-page__campaign-name">{c.name}</h4>
                    <span className={`status-badge ${statusClass(c.status)}`}>
                      {STATUS_LABELS[c.status] ?? c.status}
                    </span>
                  </div>

                  <dl className="library-page__campaign-meta">
                    <div className="library-page__meta-row">
                      <dt>状态</dt>
                      <dd>{c.status}</dd>
                    </div>
                    <div className="library-page__meta-row">
                      <dt>创建</dt>
                      <dd>{formatTime(c.created_at)}</dd>
                    </div>
                    <div className="library-page__meta-row">
                      <dt>更新</dt>
                      <dd>{formatTime(c.updated_at)}</dd>
                    </div>
                    {c.failed_stage && (
                      <div className="library-page__meta-row library-page__meta-row--error">
                        <dt>失败阶段</dt>
                        <dd>{c.failed_stage}</dd>
                      </div>
                    )}
                    {c.error_message && (
                      <div className="library-page__meta-row library-page__meta-row--error">
                        <dt>错误</dt>
                        <dd>{c.error_message}</dd>
                      </div>
                    )}
                  </dl>

                  <button
                    type="button"
                    className="btn btn--ghost library-page__continue-btn"
                    disabled={continuingId !== null}
                    onClick={() => void handleContinue(c)}
                  >
                    {continuingId === c.id
                      ? '恢复中…'
                      : c.status === 'archived'
                        ? '查看'
                        : '继续编辑'}
                  </button>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
