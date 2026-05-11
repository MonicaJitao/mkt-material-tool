import { apiClient } from '@/api/client';
import type {
  TemplateListResponse,
  CampaignCreate,
  CampaignCreateResponse,
  PlanGenerateResponse,
  PlanApproveRequest,
  PlanApproveResponse,
  ImageBatchRequest,
  ImageBatchResponse,
  ImageBatchStatusResponse,
  ImageSelectRequest,
  ImageSelectResponse,
  HtmlGenerateRequest,
  HtmlGenerateResponse,
} from '@/api/types';

export const generationApi = {
  // ── 模板 ──────────────────────────────────────────────────────

  listTemplates(): Promise<TemplateListResponse> {
    return apiClient.get<TemplateListResponse>('/api/templates');
  },

  // ── 活动 ──────────────────────────────────────────────────────

  createCampaign(body: CampaignCreate): Promise<CampaignCreateResponse> {
    return apiClient.post<CampaignCreateResponse>('/api/campaigns', body);
  },

  // ── 视觉方案 ──────────────────────────────────────────────────

  generatePlan(campaignId: string, body?: { model?: string }): Promise<PlanGenerateResponse> {
    return apiClient.post<PlanGenerateResponse>(`/api/campaigns/${campaignId}/plan/generate`, body);
  },

  approvePlan(campaignId: string, body: PlanApproveRequest): Promise<PlanApproveResponse> {
    return apiClient.post<PlanApproveResponse>(`/api/campaigns/${campaignId}/plan/approve`, body);
  },

  // ── 底图批次 ──────────────────────────────────────────────────

  createImageBatch(campaignId: string, body: ImageBatchRequest): Promise<ImageBatchResponse> {
    return apiClient.post<ImageBatchResponse>(`/api/campaigns/${campaignId}/images/batches`, body);
  },

  getImageBatch(batchId: string): Promise<ImageBatchStatusResponse> {
    return apiClient.get<ImageBatchStatusResponse>(`/api/image-batches/${batchId}`);
  },

  selectImage(campaignId: string, body: ImageSelectRequest): Promise<ImageSelectResponse> {
    return apiClient.post<ImageSelectResponse>(`/api/campaigns/${campaignId}/images/select`, body);
  },

  // ── HTML 生成 ─────────────────────────────────────────────────

  generateHtml(campaignId: string, body: HtmlGenerateRequest): Promise<HtmlGenerateResponse> {
    return apiClient.post<HtmlGenerateResponse>(`/api/campaigns/${campaignId}/html/generate`, body);
  },
};
