import { NavLink } from 'react-router-dom';
import './sidebar.css';

const quickLinks = [
  { to: '/brief', label: '当前活动' },
  { to: '/library', label: '素材资产' },
];

export function Sidebar() {
  return (
    <aside className="shell-sidebar">
      <div className="shell-sidebar__brand">
        <p className="shell-sidebar__eyebrow">MKT STUDIO</p>
        <h1>营销素材工作台</h1>
        <p>高级编辑部风格的创作流程壳，承载 Brief 到 HTML 编辑全流程。</p>
      </div>

      <nav className="shell-sidebar__nav" aria-label="快速导航">
        {quickLinks.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            className={({ isActive }) => (isActive ? 'shell-link shell-link--active' : 'shell-link')}
          >
            {link.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
