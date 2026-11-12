import { NavLink, Outlet } from 'react-router';
import { BookOpen, House, Play, Users } from 'lucide-react';

const NAV = [
  { to: '/', label: '首頁', icon: House },
  { to: '/player', label: '播放', icon: Play },
  { to: '/analytics', label: '紀錄', icon: BookOpen },
  { to: '/cast', label: '名冊', icon: Users },
];

export function ViewerLayout() {
  return (
    <div className="flex h-full flex-col bg-ground">
      <header className="flex h-14 shrink-0 flex-row items-center justify-between gap-3 border-b border-carbon-deep/13 bg-tint px-4 sm:px-14">
        <div className="flex min-w-0 flex-row items-center gap-3 whitespace-nowrap">
          <span className="truncate font-kai text-[16px] font-bold text-carbon-deep">
            <span className="sm:hidden">MV</span>
            <span className="max-sm:hidden">MV Face Recognition</span>
          </span>
          <span className="font-kai text-[12px] text-ink-muted max-sm:hidden">全民造星 IV</span>
        </div>
        {/* ponytail: four two-character links fit a 320px phone inline; a popover menu earns its
            place only if the nav grows past that. */}
        <nav aria-label="主選單" className="flex shrink-0 flex-row items-center gap-1 sm:gap-2">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex h-11 flex-row items-center gap-2 whitespace-nowrap rounded-md px-2 font-kai text-[14px] sm:h-9 sm:px-3 ${
                  isActive
                    ? 'bg-ground font-bold text-carbon-deep'
                    : 'text-carbon hover:bg-ground/60'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon
                    size={16}
                    aria-hidden="true"
                    className={`max-sm:hidden ${isActive ? 'text-stamp' : 'text-carbon-soft'}`}
                  />
                  {item.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
