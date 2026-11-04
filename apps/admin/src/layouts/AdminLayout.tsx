import { Outlet, NavLink } from 'react-router';
import { useState, useEffect } from 'react';
import {
  BookOpen,
  Cpu,
  Inbox,
  LayoutDashboard,
  Play,
  ScanFace,
  Tag,
  Users,
  Wrench,
} from 'lucide-react';
import { useFlaggedFaces } from '@mv/shared';

const sections = [
  {
    group: '核對',
    items: [
      { to: '/', label: '儀表', icon: LayoutDashboard },
      { to: '/flagging', label: '待核', icon: Inbox },
      { to: '/labelling', label: '標註', icon: Tag },
    ],
  },
  {
    group: '資料',
    items: [
      { to: '/contestants', label: '參賽者', icon: Users },
      { to: '/player', label: '播放', icon: Play },
      { to: '/analytics', label: '紀錄', icon: BookOpen },
    ],
  },
  {
    group: '生產',
    items: [
      { to: '/processing', label: '處理', icon: Cpu },
      { to: '/embedding-workbench', label: '向量', icon: ScanFace },
      { to: '/admin', label: '管理', icon: Wrench },
    ],
  },
];

type Status = 'online' | 'offline' | 'checking';
type ApiMode = 'local' | 'edge';

export function AdminLayout() {
  const [status, setStatus] = useState<Status>('checking');
  const [mode, setMode] = useState<ApiMode>('local');
  const { data: flagged = [] } = useFlaggedFaces();
  const pending = flagged.filter((f) => f.status === 'pending').length;

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch('/api/system/status');
        if (!res.ok) {
          setStatus('offline');
          return;
        }
        const data = (await res.json()) as { mode?: string; chromadb_connected?: unknown };
        setMode(
          data.mode === 'edge' || (!data.mode && data.chromadb_connected !== undefined)
            ? 'edge'
            : 'local',
        );
        setStatus('online');
      } catch {
        setStatus('offline');
      }
    };
    void check();
    const id = setInterval(check, 30000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex h-full flex-row bg-ground">
      <nav className="flex w-60 shrink-0 flex-col gap-6 border-r border-carbon-deep/13 bg-tint px-3 pb-4 pt-6">
        <div className="flex flex-col gap-1 px-2.5">
          <span className="font-kai text-[16px] font-bold leading-tight text-carbon-deep">
            MV Face Recognition
          </span>
          <span className="font-kai text-[12px] leading-tight text-ink-muted">後台 · 存根</span>
        </div>

        <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto">
          {sections.map((section) => (
            <div key={section.group} className="flex flex-col gap-0.5">
              <div className="px-2.5 pb-1.5 font-kai text-[12px] leading-tight text-ink-muted">
                {section.group}
              </div>
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `flex h-9 shrink-0 flex-row items-center gap-2.5 rounded-md px-2.5 font-kai text-[14px] ${
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
                        className={isActive ? 'text-stamp' : 'text-carbon-soft'}
                      />
                      <span className="flex-1">{item.label}</span>
                      {item.to === '/flagging' && pending > 0 ? (
                        <span className="font-mono text-[12px] font-normal tabular-nums text-stamp">
                          {pending}
                        </span>
                      ) : null}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </div>

        <div className="flex flex-row items-center gap-2 border-t border-carbon-deep/13 px-2.5 pt-3">
          <span
            className={`h-2 w-2 shrink-0 rounded-full ${
              status === 'online'
                ? 'bg-carbon'
                : status === 'offline'
                  ? 'bg-stamp'
                  : 'animate-pulse bg-ink-muted'
            }`}
          />
          <div className="flex min-w-0 flex-col gap-0.5">
            <span className="font-kai text-[12px] text-carbon">
              {status === 'online'
                ? mode === 'edge'
                  ? '雲端 API 連線中'
                  : '本機 API 連線中'
                : status === 'offline'
                  ? 'API 離線'
                  : '檢查連線中'}
            </span>
            <span className="truncate font-mono text-[12px] text-ink-muted">
              {mode === 'edge' ? window.location.host : '127.0.0.1:8000'}
            </span>
          </div>
        </div>
      </nav>

      <main className="flex min-w-0 flex-1 flex-col overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
