import { useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import './header.css';

function getStageTitle(pathname: string): string {
  if (pathname.startsWith('/plan-review')) return '方案确认';
  if (pathname.startsWith('/image-batch')) return '底图批次';
  if (pathname.startsWith('/html-generate')) return 'HTML 生成';
  if (pathname.startsWith('/html-editor')) return 'HTML 编辑';
  if (pathname.startsWith('/library')) return '素材库';
  return 'Brief';
}

export function Header() {
  const location = useLocation();
  const stageTitle = useMemo(() => getStageTitle(location.pathname), [location.pathname]);

  return (
    <header className="shell-header">
      <div>
        <p className="shell-header__meta">Campaign Workspace</p>
        <strong>{stageTitle}</strong>
      </div>
      <span className="shell-header__status">系统就绪</span>
    </header>
  );
}
