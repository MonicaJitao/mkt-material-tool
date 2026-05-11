import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import type { CampaignOut, HtmlPosterOut, ImageAssetOut, ImageBatchItem } from '@/api/types';

export type WorkflowStepId =
  | 'brief'
  | 'plan-review'
  | 'image-batch'
  | 'html-generate'
  | 'html-editor';

const WORKFLOW_STEPS: readonly WorkflowStepId[] = [
  'brief',
  'plan-review',
  'image-batch',
  'html-generate',
  'html-editor',
] as const;

export function isWorkflowStepId(id: string): id is WorkflowStepId {
  return (WORKFLOW_STEPS as readonly string[]).includes(id);
}

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

function normalizeBrief(input: Record<string, unknown> | null | undefined): Record<string, string> {
  const next = { ...DEFAULT_BRIEF };
  if (!input) return next;

  for (const [key, value] of Object.entries(input)) {
    if (Array.isArray(value)) {
      next[key] = value.map(String).join(', ');
    } else if (value == null) {
      next[key] = '';
    } else {
      next[key] = String(value);
    }
  }

  return next;
}

function imageAssetToBatchItem(asset: ImageAssetOut): ImageBatchItem {
  return {
    image_asset_id: asset.id,
    provider_task_id: asset.provider_task_id,
    status: asset.status,
    progress: asset.progress,
    preview_url: `/api/assets/${asset.id}/file`,
    local_path: asset.local_path,
    error_message: asset.error_message,
  };
}

function createInitialData() {
  return {
    campaignId: null as string | null,
    projectName: '',
    campaignName: '',
    selectedTemplateId: null as string | null,
    brief: { ...DEFAULT_BRIEF } as Record<string, string>,
    planModel: 'claude-sonnet-4-6',
    htmlModel: 'claude-sonnet-4-6',
    imageModel: 'gemini-3-pro-image-preview-async',
    imageCount: 4,
    imageSize: '9:16',
    structuredPlan: null as Record<string, unknown> | null,
    approvedPlan: null as Record<string, unknown> | null,
    generatedImages: [] as ImageBatchItem[],
    selectedImageId: null as string | null,
    activePosterId: null as string | null,
    activeVersionId: null as string | null,
    posters: [] as HtmlPosterOut[],
  };
}

function hasPlan(obj: Record<string, unknown> | null | undefined): boolean {
  return !!obj && Object.keys(obj).length > 0;
}

export interface WorkflowStore {
  campaignId: string | null;
  projectName: string;
  campaignName: string;
  selectedTemplateId: string | null;
  brief: Record<string, string>;
  planModel: string;
  htmlModel: string;
  imageModel: string;
  imageCount: number;
  imageSize: string;
  structuredPlan: Record<string, unknown> | null;
  approvedPlan: Record<string, unknown> | null;
  generatedImages: ImageBatchItem[];
  selectedImageId: string | null;
  activePosterId: string | null;
  activeVersionId: string | null;
  posters: HtmlPosterOut[];

  setCampaignMeta(
    data: Partial<
      Pick<WorkflowStore, 'campaignId' | 'projectName' | 'campaignName' | 'selectedTemplateId'>
    >,
  ): void;
  updateBrief(data: Partial<Record<string, string>>): void;
  setPlanModel(model: string): void;
  setImageSettings(data: Partial<Pick<WorkflowStore, 'imageModel' | 'imageCount' | 'imageSize'>>): void;
  setHtmlModel(model: string): void;

  setStructuredPlan(plan: Record<string, unknown> | null): void;
  setApprovedPlan(plan: Record<string, unknown> | null): void;

  setGeneratedImages(items: ImageBatchItem[]): void;
  setSelectedImageId(imageId: string | null): void;
  setHtmlResult(data: { posterId?: string | null; versionId?: string | null }): void;
  setPosters(posters: HtmlPosterOut[]): void;

  clearImageAndHtml(): void;
  clearHtmlPipeline(): void;

  loadCampaignBase(campaign: CampaignOut): void;
  loadAssets(assets: ImageAssetOut[]): void;
  loadPosters(posters: HtmlPosterOut[]): void;

  getReachableStep(): WorkflowStepId;
  canVisitStep(step: WorkflowStepId): boolean;
  reset(): void;
}

export const useWorkflowStore = create<WorkflowStore>()(
  persist(
    (set, get) => ({
      ...createInitialData(),

      setCampaignMeta(data) {
        set((s) => ({
          campaignId: data.campaignId !== undefined ? data.campaignId : s.campaignId,
          projectName: data.projectName !== undefined ? data.projectName : s.projectName,
          campaignName: data.campaignName !== undefined ? data.campaignName : s.campaignName,
          selectedTemplateId:
            data.selectedTemplateId !== undefined ? data.selectedTemplateId : s.selectedTemplateId,
        }));
      },

      updateBrief(data) {
        set((s) => ({
          brief: { ...s.brief, ...data } as Record<string, string>,
        }));
      },

      setPlanModel(model) {
        set({ planModel: model });
      },

      setImageSettings(data) {
        set((s) => ({ ...s, ...data }));
      },

      setHtmlModel(model) {
        set({ htmlModel: model });
      },

      setStructuredPlan(plan) {
        set({ structuredPlan: plan });
      },

      setApprovedPlan(plan) {
        set({ approvedPlan: plan });
      },

      setGeneratedImages(items) {
        set({ generatedImages: items });
      },

      setSelectedImageId(imageId) {
        set({ selectedImageId: imageId });
      },

      setHtmlResult(data) {
        set((s) => ({
          activePosterId: data.posterId !== undefined ? data.posterId : s.activePosterId,
          activeVersionId: data.versionId !== undefined ? data.versionId : s.activeVersionId,
        }));
      },

      setPosters(posters) {
        set({ posters });
      },

      clearImageAndHtml() {
        set({
          generatedImages: [],
          selectedImageId: null,
          activePosterId: null,
          activeVersionId: null,
          posters: [],
        });
      },

      clearHtmlPipeline() {
        set({
          activePosterId: null,
          activeVersionId: null,
          posters: [],
        });
      },

      loadCampaignBase(campaign) {
        set({
          campaignId: campaign.id,
          campaignName: campaign.name,
          selectedTemplateId: campaign.template_id,
          brief: normalizeBrief(campaign.brief),
          structuredPlan: campaign.structured_plan,
          approvedPlan: campaign.approved_plan,
        });
      },

      loadAssets(assets) {
        const candidates = assets.filter((a) => a.kind === 'candidate');
        const selected = assets.find((a) => a.kind === 'selected' || a.selected_at != null);
        set({
          generatedImages: candidates.map(imageAssetToBatchItem),
          selectedImageId: selected?.id ?? null,
        });
      },

      loadPosters(posters) {
        if (posters.length === 0) {
          set({ posters, activePosterId: null, activeVersionId: null });
          return;
        }
        const sorted = [...posters].sort(
          (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
        );
        const poster = sorted[0]!;
        const versionId =
          poster.current_version_id ??
          (poster.versions.length > 0 ? poster.versions[poster.versions.length - 1]!.id : null);
        set({
          posters,
          activePosterId: poster.id,
          activeVersionId: versionId,
        });
      },

      getReachableStep() {
        const s = get();
        if (s.activePosterId) return 'html-editor';
        if (s.selectedImageId) return 'html-generate';
        if (hasPlan(s.approvedPlan)) return 'image-batch';
        if (hasPlan(s.structuredPlan)) return 'plan-review';
        return 'brief';
      },

      canVisitStep(step) {
        const s = get();
        if (step === 'brief') return true;
        if (step === 'plan-review') {
          return !!s.campaignId && hasPlan(s.structuredPlan);
        }
        if (step === 'image-batch') {
          return !!s.campaignId && hasPlan(s.approvedPlan);
        }
        if (step === 'html-generate') {
          return !!s.campaignId && hasPlan(s.approvedPlan) && !!s.selectedImageId;
        }
        if (step === 'html-editor') {
          return !!s.campaignId && !!s.selectedImageId && !!s.activePosterId;
        }
        return false;
      },

      reset() {
        set(createInitialData());
      },
    }),
    {
      name: 'mkt-material-workflow',
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        campaignId: state.campaignId,
        projectName: state.projectName,
        campaignName: state.campaignName,
        selectedTemplateId: state.selectedTemplateId,
        brief: state.brief,
        planModel: state.planModel,
        imageModel: state.imageModel,
        htmlModel: state.htmlModel,
        imageCount: state.imageCount,
        imageSize: state.imageSize,
        structuredPlan: state.structuredPlan,
        approvedPlan: state.approvedPlan,
        generatedImages: state.generatedImages,
        selectedImageId: state.selectedImageId,
        activePosterId: state.activePosterId,
        activeVersionId: state.activeVersionId,
        posters: state.posters,
      }),
    },
  ),
);
