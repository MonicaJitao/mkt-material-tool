import { apiClient } from '@/api/client';
import type {
  ProjectListResponse,
  ProjectOut,
  CampaignListResponse,
  CampaignOut,
  ImageAssetOut,
  HtmlPosterOut,
} from '@/api/types';

export const assetsApi = {
  /** 列出所有项目 */
  listProjects(): Promise<ProjectListResponse> {
    return apiClient.get<ProjectListResponse>('/api/projects');
  },

  /** 获取项目详情 */
  getProject(projectId: string): Promise<ProjectOut> {
    return apiClient.get<ProjectOut>(`/api/projects/${projectId}`);
  },

  /** 列出活动（可按 project_id、status 筛选） */
  listCampaigns(params?: {
    project_id?: string;
    status?: string;
  }): Promise<CampaignListResponse> {
    return apiClient.get<CampaignListResponse>('/api/campaigns', params);
  },

  /** 获取活动详情 */
  getCampaign(campaignId: string): Promise<CampaignOut> {
    return apiClient.get<CampaignOut>(`/api/campaigns/${campaignId}`);
  },

  /** 列出活动下的底图资产 */
  listCampaignAssets(
    campaignId: string,
    kind?: 'candidate' | 'selected',
  ): Promise<{ items: ImageAssetOut[] }> {
    return apiClient.get<{ items: ImageAssetOut[] }>(
      `/api/campaigns/${campaignId}/assets`,
      kind ? { kind } : undefined,
    );
  },

  /** 列出活动下的 HTML 海报 */
  listCampaignPosters(campaignId: string): Promise<HtmlPosterOut[]> {
    return apiClient.get<HtmlPosterOut[]>(`/api/campaigns/${campaignId}/html`);
  },

  /** 底图文件 URL（供 <img src> 使用） */
  getAssetFileUrl(assetId: string): string {
    return `/api/assets/${assetId}/file`;
  },
};
