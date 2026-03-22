import { Outlet, NavLink } from 'react-router';
import { useState, useEffect } from 'react';

const navItems = [
  { to: '/', icon: '📊', label: 'Dashboard' },
  { to: '/player', icon: '▶️', label: 'Video Player' },
  { to: '/contestants', icon: '👥', label: 'Contestants' },
  { to: '/ingestion', icon: '📤', label: 'Ingestion' },
  { to: '/analytics', icon: '📈', label: 'Analytics' },
  { to: '/flagging', icon: '🚩', label: 'Flagging' },
  { separator: true },
  { to: '/processing', icon: '⚙️', label: 'Processing' },
  { to: '/embedding-workbench', icon: '🧬', label: 'Embeddings' },
  { to: '/admin', icon: '🔐', label: 'Admin' },
] as const;

type Status = 'online' | 'offline' | 'checking';

export function AdminLayout() {
  const [status, setStatus] = useState<Status>('checking');

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch('/api/system/status');
        setStatus(res.ok ? 'online' : 'offline');
      } catch {
        setStatus('offline');
      }
    };
    check();
    const id = setInterval(check, 30000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-50 h-15 flex items-center justify-between px-5 border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm">
        <h1 className="text-lg font-semibold text-slate-100 font-mono">MV Face Recognition</h1>
        <div className="flex items-center gap-2 text-xs">
          <span className={`w-2 h-2 rounded-full ${status === 'online' ? 'bg-green-500' : status === 'offline' ? 'bg-red-500' : 'bg-yellow-500 animate-pulse'}`} />
          <span className="text-slate-500">{status}</span>
        </div>
      </header>

      <div className="flex flex-1">
        {/* Sidebar */}
        <nav className="w-60 shrink-0 bg-slate-900 border-r border-slate-800 py-4 overflow-y-auto">
          {navItems.map((item, i) => {
            if ('separator' in item) {
              return <div key={i} className="h-px bg-slate-800 mx-4 my-2" />;
            }
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 px-4 py-2 mx-2 rounded-md text-sm transition-colors ${
                    isActive
                      ? 'bg-orange-600 text-white font-semibold'
                      : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                  }`
                }
              >
                <span className="text-base leading-none">{item.icon}</span>
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Main content */}
        <main className="flex-1 p-8 overflow-y-auto bg-slate-950">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
