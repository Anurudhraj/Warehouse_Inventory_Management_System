import { NavLink } from 'react-router-dom';

import { HealthIndicator } from '@/components/layout/health-indicator';
import { dashboardNavItem, MODULE_GROUPS, modulesInGroup } from '@/config/modules';
import { env } from '@/config/env';
import { cn } from '@/lib/utils/cn';

interface SidebarProps {
  open: boolean;
  onNavigate: () => void;
}

const linkBase =
  'group flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] font-medium transition-colors';

function navLinkClass({ isActive }: { isActive: boolean }): string {
  return cn(
    linkBase,
    isActive
      ? 'bg-sidebar-accent text-sidebar-accent-foreground shadow-xs ring-1 ring-sidebar-active/40'
      : 'text-sidebar-foreground hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground',
  );
}

export function Sidebar({ open, onNavigate }: SidebarProps) {
  const DashboardIcon = dashboardNavItem.icon;

  return (
    <aside
      id="app-sidebar"
      data-state={open ? 'open' : 'closed'}
      className={cn(
        'bg-sidebar text-sidebar-foreground border-sidebar-border fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col border-r',
        'transition-transform duration-200 ease-out lg:static lg:translate-x-0',
        open ? 'translate-x-0' : '-translate-x-full',
      )}
      aria-label="Primary navigation"
    >
      <div className="border-sidebar-border flex h-14 items-center gap-2.5 border-b px-4">
        <img src="/favicon.svg" alt="" className="size-7" aria-hidden="true" />
        <div className="flex flex-col leading-none">
          <span className="text-sidebar-accent-foreground text-sm font-semibold tracking-tight">
            {env.appName}
          </span>
          <span className="text-sidebar-muted mt-0.5 text-[10px] tracking-widest uppercase">
            Inventory Platform
          </span>
        </div>
      </div>

      <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
        <div>
          <NavLink
            to={dashboardNavItem.path}
            end
            className={navLinkClass}
            onClick={onNavigate}
          >
            <DashboardIcon className="size-4 shrink-0 opacity-80" aria-hidden="true" />
            {dashboardNavItem.name}
          </NavLink>
        </div>

        {MODULE_GROUPS.filter((group) => group !== 'Overview').map((group) => {
          const modules = modulesInGroup(group);
          if (modules.length === 0) return null;
          return (
            <div key={group} className="space-y-1">
              <p className="text-sidebar-muted px-2.5 pb-1 text-[10px] font-semibold tracking-widest uppercase">
                {group}
              </p>
              {modules.map((module) => {
                const Icon = module.icon;
                return (
                  <NavLink
                    key={module.key}
                    to={module.path}
                    className={navLinkClass}
                    onClick={onNavigate}
                    title={module.summary}
                  >
                    <Icon className="size-4 shrink-0 opacity-80" aria-hidden="true" />
                    <span className="truncate">{module.name}</span>
                  </NavLink>
                );
              })}
            </div>
          );
        })}
      </nav>

      <div className="border-sidebar-border space-y-1 border-t px-3 py-3">
        <HealthIndicator />
        <p className="text-sidebar-muted px-2.5 pb-1 text-[10px]">
          Part 1 · Foundation · {env.appEnv}
        </p>
      </div>
    </aside>
  );
}
