import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Bell, ChevronRight, LogOut, Menu, Moon, Search, Sun, User } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { MODULES_BY_KEY } from '@/config/modules';
import { useAuth } from '@/features/auth/auth-context';
import { useTheme } from '@/hooks/use-theme';
import { initials } from '@/lib/utils/format';

interface TopbarProps {
  onToggleSidebar: () => void;
}

function useBreadcrumbs() {
  const { pathname } = useLocation();
  const segments = pathname.split('/').filter(Boolean);
  const crumbs = [{ label: 'Home', to: '/' }];

  if (segments.length === 0) return [{ label: 'Dashboard', to: '/' }];

  const [first, second] = segments;
  if (first === 'system') {
    crumbs.push({ label: 'System', to: '/' });
    crumbs.push({ label: second === 'health' ? 'Health' : (second ?? 'Overview'), to: pathname });
    return crumbs;
  }
  if (first === 'administration') {
    crumbs.push({ label: 'Administration', to: pathname });
    crumbs.push({ label: second === 'permissions' ? 'Permissions' : second === 'roles' ? 'Roles' : 'Users', to: pathname });
    return crumbs;
  }
  if (first === 'profile') {
    crumbs.push({ label: 'My profile', to: pathname });
    return crumbs;
  }

  const module = MODULES_BY_KEY[first];
  crumbs.push({ label: module?.name ?? first, to: module?.path ?? pathname });
  if (second) crumbs.push({ label: second, to: pathname });
  return crumbs;
}

export function Topbar({ onToggleSidebar }: TopbarProps) {
  const { theme, toggleTheme } = useTheme();
  const { user, signOut, isPlatformAdmin } = useAuth();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const crumbs = useBreadcrumbs();

  const displayName = user
    ? user.full_name || `${user.first_name} ${user.last_name}`.trim()
    : 'Signed out';
  const roleLabel = isPlatformAdmin
    ? 'Platform administrator'
    : (user?.job_title || user?.organization?.name || 'Warehouse user');

  async function handleSignOut() {
    setMenuOpen(false);
    await signOut();
    navigate('/login', { replace: true });
  }

  return (
    <header className="bg-card/85 border-border sticky top-0 z-30 flex h-14 items-center gap-3 border-b px-3 backdrop-blur-sm sm:px-5">
      <Button
        variant="ghost"
        size="icon"
        className="lg:hidden"
        onClick={onToggleSidebar}
        aria-label="Toggle navigation"
      >
        <Menu className="size-4" />
      </Button>

      <nav aria-label="Breadcrumb" className="hidden min-w-0 items-center gap-1.5 text-sm sm:flex">
        {crumbs.map((crumb, index) => {
          const isLast = index === crumbs.length - 1;
          return (
            <span key={`${crumb.label}-${index}`} className="flex min-w-0 items-center gap-1.5">
              {index > 0 ? (
                <ChevronRight className="text-muted-foreground size-3.5 shrink-0" aria-hidden="true" />
              ) : null}
              {isLast ? (
                <span className="truncate font-medium" aria-current="page">
                  {crumb.label}
                </span>
              ) : (
                <Link to={crumb.to} className="text-muted-foreground hover:text-foreground truncate transition-colors">
                  {crumb.label}
                </Link>
              )}
            </span>
          );
        })}
      </nav>

      <div className="relative ms-auto hidden w-full max-w-xs md:block">
        <Search
          className="text-muted-foreground pointer-events-none absolute start-2.5 top-1/2 size-3.5 -translate-y-1/2"
          aria-hidden="true"
        />
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search SKUs, orders, locations…"
          aria-label="Global search"
          className="h-9 ps-8 text-[13px]"
        />
      </div>

      <div className="ms-auto flex items-center gap-1 md:ms-0">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
        >
          {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </Button>

        <Button variant="ghost" size="icon" aria-label="Notifications" className="relative">
          <Bell className="size-4" />
          <span className="bg-danger absolute end-2 top-2 size-1.5 rounded-full" aria-hidden="true" />
        </Button>

        <div className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((open) => !open)}
            className="hover:bg-muted flex items-center gap-2 rounded-md py-1.5 pe-2 ps-1.5 transition-colors"
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            aria-label={`Account menu for ${displayName}`}
          >
            <span className="bg-primary text-primary-foreground flex size-7 items-center justify-center rounded-full text-[11px] font-semibold">
              {initials(displayName)}
            </span>
            <span className="hidden text-left leading-tight sm:block">
              <span className="block text-xs font-medium">{displayName}</span>
              <span className="text-muted-foreground block text-[10px]">{roleLabel}</span>
            </span>
          </button>

          {menuOpen ? (
            <>
              <div
                className="fixed inset-0 z-40"
                role="presentation"
                onClick={() => setMenuOpen(false)}
              />
              <div
                role="menu"
                className="bg-popover text-popover-foreground border-border animate-fade-in absolute end-0 z-50 mt-2 w-56 rounded-lg border p-1.5 shadow-overlay"
              >
                <div className="border-border mb-1 flex items-center justify-between gap-2 border-b px-2.5 pb-2 pt-1">
                  <span className="truncate text-xs font-medium">{user?.email}</span>
                  {isPlatformAdmin ? (
                    <Badge variant="primary">Admin</Badge>
                  ) : (
                    <Badge variant="outline">{user?.status ?? 'unknown'}</Badge>
                  )}
                </div>
                <MenuItem
                  icon={<User className="size-3.5" />}
                  label="Profile"
                  onClick={() => {
                    setMenuOpen(false);
                    navigate('/profile');
                  }}
                />
                <MenuItem
                  icon={<LogOut className="size-3.5" />}
                  label="Sign out"
                  onClick={() => void handleSignOut()}
                />
                {user?.must_change_password ? (
                  <p className="text-warning-foreground px-2.5 pt-2 pb-1 text-[10px]">
                    An administrator issued your current password — change it in Profile.
                  </p>
                ) : null}
              </div>
            </>
          ) : null}
        </div>
      </div>
    </header>
  );
}

function MenuItem({
  icon,
  label,
  disabled,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  disabled?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      onClick={onClick}
      className="hover:bg-muted flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] transition-colors disabled:pointer-events-none disabled:opacity-50"
    >
      <span className="text-muted-foreground">{icon}</span>
      {label}
    </button>
  );
}
