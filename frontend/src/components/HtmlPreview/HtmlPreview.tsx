import { htmlApi } from '@/api/html';
import './html-preview.css';

interface HtmlPreviewProps {
  versionId: string | null;
  /** 可选：直接传入 HTML 内容（用于编辑器实时预览） */
  htmlContent?: string;
  className?: string;
}

export function HtmlPreview({ versionId, htmlContent, className }: HtmlPreviewProps) {
  const src = versionId ? htmlApi.getPreviewUrl(versionId) : undefined;

  // 如果有 htmlContent（编辑器实时预览），用 srcdoc
  if (htmlContent !== undefined) {
    return (
      <div className={`html-preview ${className ?? ''}`}>
        <iframe
          className="html-preview__frame"
          srcDoc={htmlContent}
          sandbox="allow-same-origin"
          title="HTML 海报预览"
        />
      </div>
    );
  }

  // 否则从后端获取 raw HTML（已发布版本预览）
  if (!src) {
    return (
      <div className={`html-preview ${className ?? ''}`}>
        <div className="html-preview__empty">暂无预览内容</div>
      </div>
    );
  }

  return (
    <div className={`html-preview ${className ?? ''}`}>
      <iframe
        className="html-preview__frame"
        src={src}
        sandbox="allow-same-origin"
        title="HTML 海报预览"
      />
    </div>
  );
}
