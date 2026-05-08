export interface WorkflowStep {
  id: string;
  path: string;
  label: string;
  hint: string;
}

export const workflowSteps: WorkflowStep[] = [
  { id: 'brief', path: '/brief', label: 'Brief', hint: '填写营销简报与目标' },
  { id: 'plan-review', path: '/plan-review', label: '方案确认', hint: '审阅并确认结构化方案' },
  { id: 'image-batch', path: '/image-batch', label: '底图批次', hint: '批量生成并选择底图' },
  { id: 'html-generate', path: '/html-generate', label: 'HTML 生成', hint: '基于选中底图产出海报' },
  { id: 'html-editor', path: '/html-editor', label: 'HTML 编辑', hint: '预览、编辑并保存版本' },
  { id: 'library', path: '/library', label: '素材库', hint: '管理活动资产与历史版本' },
];
