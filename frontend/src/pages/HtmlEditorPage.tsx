import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { htmlApi } from '@/api/html';
import { assetsApi } from '@/api/assets';
import { HtmlPreview } from '@/components/HtmlPreview/HtmlPreview';
import { HtmlEditor } from '@/components/HtmlEditor/HtmlEditor';
import type { HtmlVersionOut } from '@/api/types';
import { useWorkflowStore } from '@/store/workflowStore';
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

  const campaignId = useWorkflowStore((s) => s.campaignId) ?? '';
  const selectedImageId = useWorkflowStore((s) => s.selectedImageId) ?? '';
  const posterId = useWorkflowStore((s) => s.activePosterId) ?? '';
  const storeVersionId = useWorkflowStore((s) => s.activeVersionId) ?? '';

  const setHtmlResult = useWorkflowStore((s) => s.setHtmlResult);
  const loadPosters = useWorkflowStore((s) => s.loadPosters);

  const [activeTab, setActiveTab] = useState<'preview' | 'editor'>('preview');
  const [selectedVersionId, setSelectedVersionId] = useState(storeVersionId);
  const [editorContent, setEditorContent] = useState('');
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const [hydrateError, setHydrateError] = useState<string | null>(null);

  useEffect(() => {
    if (storeVersionId) {
      setSelectedVersionId(storeVersionId);
    }
  }, [storeVersionId, posterId]);

  useEffect(() => {
    if (!campaignId) {
      navigate('/brief');
      return;
    }
    if (!selectedImageId) {
      navigate('/image-batch');
    }
  }, [campaignId, selectedImageId, navigate]);

  useEffect(() => {
    if (!campaignId || !selectedImageId || posterId) return;

    let cancelled = false;
    setHydrateError(null);
    assetsApi
      .listCampaignPosters(campaignId)
      .then((posters) => {
        if (cancelled) return;
        if (posters.length === 0) {
          navigate('/html-generate');
          return;
        }
        loadPosters(posters);
      })
      .catch(() => {
        if (!cancelled) {
          setHydrateError('无法加载海报列表，请返回 HTML 生成页重试');
        }
      });

    return () => {
      cancelled = true;
    };
  }, [campaignId, selectedImageId, posterId, navigate, loadPosters]);

  const posterQuery = useQuery({
    queryKey: ['poster', posterId],
    queryFn: () => htmlApi.getPoster(posterId),
    enabled: !!posterId,
  });

  useEffect(() => {
    const data = posterQuery.data;
    if (!data || !posterId) return;
    if (selectedVersionId) return;
    const last = data.versions.length > 0 ? data.versions[data.versions.length - 1] : undefined;
    const vid = storeVersionId || data.current_version_id || last?.id;
    if (vid) {
      setSelectedVersionId(vid);
      if (!storeVersionId) {
        setHtmlResult({ posterId, versionId: vid });
      }
    }
  }, [posterQuery.data, posterId, storeVersionId, selectedVersionId, setHtmlResult]);

  const versionQuery = useQuery({
    queryKey: ['html-version', selectedVersionId],
    queryFn: () => htmlApi.getVersionContent(selectedVersionId!),
    enabled: !!selectedVersionId,
  });

  useEffect(() => {
    if (versionQuery.data && !dirty) {
      setEditorContent(versionQuery.data.html);
    }
  }, [versionQuery.data, dirty]);

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
      queryClient.invalidateQueries({ queryKey: ['poster', posterId] });
      setSelectedVersionId(data.version_id);
      setHtmlResult({ posterId, versionId: data.version_id });
    },
    onError: (err: Error) => {
      setError(err.message ?? '保存失败，请重试');
    },
  });

  const regenerateMutation = useMutation({
    mutationFn: () =>
      htmlApi.regenerateHtml(campaignId, {
        selected_image_id: selectedImageId,
      }),
    onSuccess: (data) => {
      setDirty(false);
      setError(null);
      setHtmlResult({ posterId: data.poster_id, versionId: data.version_id });
      setSelectedVersionId(data.version_id);
      queryClient.invalidateQueries({ queryKey: ['poster', data.poster_id] });
    },
    onError: (err: Error) => {
      setError(err.message ?? '重新生成失败，请重试');
    },
  });

  const handleVersionSwitch = useCallback((versionId: string) => {
    if (dirty) {
      const ok = window.confirm('当前有未保存的编辑，切换版本将丢失修改。确定切换？');
      if (!ok) return;
    }
    setDirty(false);
    setError(null);
    setSelectedVersionId(versionId);
    setHtmlResult({ posterId: posterId || null, versionId });
  }, [dirty, posterId, setHtmlResult]);

  const handleEditorChange = useCallback((value: string) => {
    setEditorContent(value);
    setDirty(true);
    setSavedNotice(null);
  }, []);

  const handleExport = useCallback(() => {
    if (!selectedVersionId) return;
    const a = document.createElement('a');
    a.href = `/api/html/${selectedVersionId}/export`;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }, [selectedVersionId]);

  const versions: HtmlVersionOut[] = posterQuery.data?.versions ?? [];
  const isLoading = !!posterId && (posterQuery.isLoading || versionQuery.isLoading);
  const isSaving = saveMutation.isPending;
  const isRegenerating = regenerateMutation.isPending;

  return (
    <section className="html-editor-page">
      <header className="html-editor-page__header">
        <div className="html-editor-page__title-group">
          <h2>HTML 预览与编辑</h2>
          {savedNotice && <span className="html-editor-page__saved-notice">{savedNotice}</span>}
        </div>

        <div className="html-editor-page__header-controls">
          {versions.length > 0 && (
            <select
              className="html-editor-page__version-select"
              aria-label="切换 HTML 版本"
              value={selectedVersionId}
              onChange={(e) => handleVersionSwitch(e.target.value)}
            >
              {[...versions].reverse().map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.version_no} · {sourceLabel(v.source)} · {formatTime(v.created_at)}
                </option>
              ))}
            </select>
          )}
        </div>

        <div className="html-editor-page__actions">
          <button
            type="button"
            className="btn btn--ghost"
            onClick={handleExport}
            disabled={!selectedVersionId}
          >
            导出自包含 HTML
          </button>
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
            disabled={isSaving || isRegenerating || !dirty || !editorContent.trim() || !posterId}
          >
            {isSaving ? '保存中…' : '保存为新版本'}
          </button>
        </div>
      </header>

      {hydrateError && <p className="brief-form__error">{hydrateError}</p>}
      {error && <p className="brief-form__error">{error}</p>}

      <div className="html-editor-page__tabs" role="tablist" aria-label="HTML 编辑视图">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'preview'}
          className={`html-editor-page__tab ${activeTab === 'preview' ? 'html-editor-page__tab--active' : ''}`}
          onClick={() => setActiveTab('preview')}
        >
          预览
          {dirty && <span className="html-editor-page__dirty-badge">未保存</span>}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === 'editor'}
          className={`html-editor-page__tab ${activeTab === 'editor' ? 'html-editor-page__tab--active' : ''}`}
          onClick={() => setActiveTab('editor')}
        >
          源码编辑
          {dirty && <span className="html-editor-page__dirty-badge">未保存</span>}
        </button>
      </div>

      <div className="html-editor-page__body">
        {activeTab === 'preview' && (
          <div className="html-editor-page__preview-panel" role="tabpanel">
            {!posterId ? (
              <div className="html-editor-page__loading shimmer">正在恢复海报…</div>
            ) : isLoading ? (
              <div className="html-editor-page__loading shimmer">加载中…</div>
            ) : (
              <HtmlPreview
                versionId={selectedVersionId}
                className="html-editor-page__preview"
              />
            )}
          </div>
        )}

        {activeTab === 'editor' && (
          <div className="html-editor-page__editor-panel" role="tabpanel">
            <div className="html-editor-page__editor-container">
              {!posterId ? (
                <div className="html-editor-page__loading shimmer">正在恢复海报…</div>
              ) : isLoading ? (
                <div className="html-editor-page__loading shimmer">加载中…</div>
              ) : (
                <HtmlEditor
                  value={editorContent}
                  onChange={handleEditorChange}
                  className="html-editor-page__editor"
                />
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
