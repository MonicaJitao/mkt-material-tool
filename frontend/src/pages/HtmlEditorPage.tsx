import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { htmlApi } from '@/api/html';
import { HtmlPreview } from '@/components/HtmlPreview/HtmlPreview';
import { HtmlEditor } from '@/components/HtmlEditor/HtmlEditor';
import type { HtmlVersionOut } from '@/api/types';
import './html-editor-page.css';

function formatTime(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function sourceLabel(source: string): string {
  switch (source) {
    case 'model': return '模型生成';
    case 'manual_edit': return '手动编辑';
    case 'regenerate': return '重新生成';
    default: return source;
  }
}

export function HtmlEditorPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const campaignId = sessionStorage.getItem('activeCampaignId') ?? '';
  const selectedImageId = sessionStorage.getItem('selectedImageId') ?? '';
  const posterId = sessionStorage.getItem('activePosterId') ?? '';
  const initialVersionId = sessionStorage.getItem('activeVersionId') ?? '';

  // 当前选中的版本 ID
  const [selectedVersionId, setSelectedVersionId] = useState(initialVersionId);
  // 编辑器中的 HTML 内容
  const [editorContent, setEditorContent] = useState('');
  // 是否有未保存的编辑
  const [dirty, setDirty] = useState(false);
  // 错误信息
  const [error, setError] = useState<string | null>(null);
  // 保存成功提示
  const [savedNotice, setSavedNotice] = useState<string | null>(null);

  // ── 重定向检查 ────────────────────────────────────────────────
  useEffect(() => {
    if (!campaignId) navigate('/brief');
    else if (!selectedImageId) navigate('/image-batch');
    else if (!posterId) navigate('/html-generate');
  }, [campaignId, selectedImageId, posterId, navigate]);

  // ── 查询海报详情与版本列表 ─────────────────────────────────────
  const posterQuery = useQuery({
    queryKey: ['poster', posterId],
    queryFn: () => htmlApi.getPoster(posterId),
    enabled: !!posterId,
  });

  // ── 查询当前选中版本的内容 ─────────────────────────────────────
  const versionQuery = useQuery({
    queryKey: ['html-version', selectedVersionId],
    queryFn: () => htmlApi.getVersionContent(selectedVersionId!),
    enabled: !!selectedVersionId,
  });

  // 版本内容加载后填充编辑器（仅在非 dirty 时）
  useEffect(() => {
    if (versionQuery.data && !dirty) {
      setEditorContent(versionQuery.data.html);
    }
  }, [versionQuery.data, dirty]);

  // ── 保存版本 ──────────────────────────────────────────────────
  const saveMutation = useMutation({
    mutationFn: () =>
      htmlApi.saveVersion(posterId, {
        source: 'manual_edit',
        html: editorContent,
      }),
    onSuccess: (data) => {
      setDirty(false);
      setError(null);
      setSavedNotice(`已保存为版本 v${data.version_no}`);
      setTimeout(() => setSavedNotice(null), 3000);
      // 刷新海报版本列表
      queryClient.invalidateQueries({ queryKey: ['poster', posterId] });
      // 切换到新版本
      setSelectedVersionId(data.version_id);
      sessionStorage.setItem('activeVersionId', data.version_id);
    },
    onError: (err: Error) => {
      setError(err.message ?? '保存失败，请重试');
    },
  });

  // ── 重新生成 HTML ──────────────────────────────────────────────
  const regenerateMutation = useMutation({
    mutationFn: () =>
      htmlApi.regenerateHtml(campaignId, {
        selected_image_id: selectedImageId,
      }),
    onSuccess: (data) => {
      setDirty(false);
      setError(null);
      sessionStorage.setItem('activePosterId', data.poster_id);
      sessionStorage.setItem('activeVersionId', data.version_id);
      setSelectedVersionId(data.version_id);
      // 刷新海报详情
      queryClient.invalidateQueries({ queryKey: ['poster', data.poster_id] });
    },
    onError: (err: Error) => {
      setError(err.message ?? '重新生成失败，请重试');
    },
  });

  // ── 版本切换 ──────────────────────────────────────────────────
  const handleVersionSwitch = useCallback((versionId: string) => {
    if (dirty) {
      const ok = window.confirm('当前有未保存的编辑，切换版本将丢失修改。确定切换？');
      if (!ok) return;
    }
    setDirty(false);
    setError(null);
    setSelectedVersionId(versionId);
    sessionStorage.setItem('activeVersionId', versionId);
  }, [dirty]);

  // ── 编辑器内容变化 ─────────────────────────────────────────────
  const handleEditorChange = useCallback((value: string) => {
    setEditorContent(value);
    setDirty(true);
    setSavedNotice(null);
  }, []);

  // ── 预览模式：dirty 时用 srcdoc 实时预览，否则用版本 URL ───────
  const previewHtml = dirty ? editorContent : undefined;

  const versions: HtmlVersionOut[] = posterQuery.data?.versions ?? [];
  const isLoading = posterQuery.isLoading || versionQuery.isLoading;
  const isSaving = saveMutation.isPending;
  const isRegenerating = regenerateMutation.isPending;

  return (
    <section className="html-editor-page">
      {/* ── 顶部栏 ─────────────────────────────────────────────── */}
      <header className="html-editor-page__header">
        <div className="html-editor-page__title-group">
          <h2>HTML 预览与编辑</h2>
          {dirty && <span className="html-editor-page__dirty-badge">未保存</span>}
          {savedNotice && <span className="html-editor-page__saved-notice">{savedNotice}</span>}
        </div>
        <div className="html-editor-page__actions">
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => navigate('/html-generate')}
            disabled={isSaving || isRegenerating}
          >
            返回生成页
          </button>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => regenerateMutation.mutate()}
            disabled={isSaving || isRegenerating || !selectedImageId}
          >
            {isRegenerating ? '重新生成中…' : '重新生成 HTML'}
          </button>
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => saveMutation.mutate()}
            disabled={isSaving || isRegenerating || !dirty || !editorContent.trim()}
          >
            {isSaving ? '保存中…' : '保存为新版本'}
          </button>
        </div>
      </header>

      {error && <p className="brief-form__error">{error}</p>}

      {/* ── 主体布局：左预览 / 右编辑+版本 ─────────────────────── */}
      <div className="html-editor-page__body">
        {/* 左侧：iframe 预览 */}
        <div className="html-editor-page__preview-panel">
          <div className="html-editor-page__panel-label">
            预览
            {dirty && <span className="html-editor-page__live-badge">实时</span>}
          </div>
          {isLoading ? (
            <div className="html-editor-page__loading shimmer">加载中…</div>
          ) : (
            <HtmlPreview
              versionId={dirty ? null : selectedVersionId}
              htmlContent={previewHtml}
              className="html-editor-page__preview"
            />
          )}
        </div>

        {/* 右侧：编辑器 + 版本时间线 */}
        <div className="html-editor-page__editor-panel">
          <div className="html-editor-page__panel-label">源码编辑</div>
          <div className="html-editor-page__editor-container">
            {isLoading ? (
              <div className="html-editor-page__loading shimmer">加载中…</div>
            ) : (
              <HtmlEditor
                value={editorContent}
                onChange={handleEditorChange}
                className="html-editor-page__editor"
              />
            )}
          </div>

          {/* 版本时间线 */}
          <div className="html-editor-page__versions">
            <div className="html-editor-page__panel-label">版本历史</div>
            {versions.length === 0 ? (
              <p className="brief-form__hint">暂无版本记录</p>
            ) : (
              <ul className="html-editor-page__version-list">
                {[...versions].reverse().map((v) => (
                  <li
                    key={v.id}
                    className={`html-editor-page__version-item ${
                      v.id === selectedVersionId ? 'html-editor-page__version-item--active' : ''
                    }`}
                    onClick={() => handleVersionSwitch(v.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        handleVersionSwitch(v.id);
                      }
                    }}
                  >
                    <span className="html-editor-page__version-no">v{v.version_no}</span>
                    <span className="html-editor-page__version-source">{sourceLabel(v.source)}</span>
                    <span className="html-editor-page__version-time">{formatTime(v.created_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
