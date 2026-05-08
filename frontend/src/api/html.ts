import { apiClient } from '@/api/client';
import type {
  HtmlVersionContent,
  HtmlVersionSaveRequest,
  HtmlVersionSaveResponse,
  HtmlPosterOut,
  HtmlGenerateRequest,
  HtmlGenerateResponse,
} from '@/api/types';

export const htmlApi = {
  /** 获取指定版本的 HTML 内容 */
  getVersionContent(versionId: string): Promise<HtmlVersionContent> {
    return apiClient.get<HtmlVersionContent>(`/api/html/${versionId}`);
  },

  /** 获取海报详情及版本列表 */
  getPoster(posterId: string): Promise<HtmlPosterOut> {
    return apiClient.get<HtmlPosterOut>(`/api/html/poster/${posterId}`);
  },

  /** 列出活动下所有 HTML 海报 */
  listPosters(campaignId: string): Promise<HtmlPosterOut[]> {
    return apiClient.get<HtmlPosterOut[]>(`/api/campaigns/${campaignId}/html`);
  },

  /** 保存手动编辑版本（不覆盖旧版本） */
  saveVersion(posterId: string, body: HtmlVersionSaveRequest): Promise<HtmlVersionSaveResponse> {
    return apiClient.post<HtmlVersionSaveResponse>(`/api/html/${posterId}/versions`, body);
  },

  /** 基于当前底图重新生成 HTML */
  regenerateHtml(campaignId: string, body: HtmlGenerateRequest): Promise<HtmlGenerateResponse> {
    return apiClient.post<HtmlGenerateResponse>(`/api/campaigns/${campaignId}/html/generate`, body);
  },

  /** 预览 URL（供 iframe src 使用，返回 text/html） */
  getPreviewUrl(versionId: string): string {
    return `/api/html/${versionId}/preview`;
  },
};
