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
      <header className="flex h-14 shrink-0 flex-row items-center justify-between border-b border-carbon-deep/13 bg-tint px-14">
        <div className="flex flex-row items-center gap-3">
          <span className="font-kai text-[16px] font-bold text-carbon-deep">
            MV Face Recognition
          </span>
          <span className="font-kai text-[12px] text-ink-muted">全民造星 IV</span>
        </div>
        <nav className="flex flex-row items-center gap-2">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex h-9 flex-row items-center gap-2 rounded-md px-3 font-kai text-[14px] ${
                  isActive
                    ? 'bg-ground font-bold text-carbon-deep'
                    : 'text-carbon hover:bg-ground/60'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon size={16} className={isActive ? 'text-stamp' : 'text-carbon-soft'} />
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
