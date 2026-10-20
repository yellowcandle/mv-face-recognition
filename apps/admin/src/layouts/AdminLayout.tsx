import { Outlet, NavLink } from 'react-router';
import { useState, useEffect } from 'react';

/**
 * 存根 — the office copy of the request slip. The punched spine carries the folio;
 * the cabinet beside it is the filing index: every section is a tab in the drawer.
 */
const sections = [
  {
    group: '核對',
    latin: 'TRIAGE',
    items: [
      { to: '/', label: '儀表', latin: 'DESK' },
      { to: '/flagging', label: '待核', latin: 'FLAGS' },
      { to: '/labelling', label: '標註', latin: 'LABEL' },
    ],
  },
  {
    group: '資料',
    latin: 'RECORDS',
    items: [
      { to: '/contestants', label: '參賽者', latin: 'CAST' },
      { to: '/player', label: '播放', latin: 'PLAYER' },
      { to: '/analytics', label: '紀錄', latin: 'LEDGER' },
    ],
  },
  {
    group: '生產',
    latin: 'PIPELINE',
    items: [
      { to: '/processing', label: '處理', latin: 'PROCESS' },
      { to: '/embedding-workbench', label: '向量', latin: 'EMBED' },
      { to: '/admin', label: '管理', latin: 'ADMIN' },
    ],
  },
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
    void check();
    const id = setInterval(check, 30000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex h-full flex-row bg-paper">
      {/* Folio spine */}
      <div className="flex w-[76px] shrink-0 flex-col items-center justify-between border-r border-carbon/30 bg-paper-dark py-8">
        <div className="flex flex-col items-center gap-6">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-[22px] w-[22px] rounded-full border border-carbon/35 bg-paper-deep shadow-[inset_0_1px_2px_rgba(43,47,107,0.25)]"
            />
          ))}
        </div>
        <div className="flex flex-col items-center gap-2.5">
          <span className="font-mono text-[10px] tracking-[0.22em] text-carbon-soft">NO.</span>
          <span className="font-mono text-[26px] text-carbon">02</span>
          <span className="h-11 w-px bg-carbon/30" />
          <span className="font-kai text-[12px] text-carbon-soft">存根</span>
        </div>
        <div className="font-mono text-[9px] tracking-[0.18em] text-carbon-soft">LOCAL</div>
      </div>

      {/* Filing cabinet */}
      <nav className="flex w-[216px] shrink-0 flex-col border-r border-carbon/30 bg-paper-dark/60 px-3 py-6">
        <div className="flex flex-col gap-0.5 px-2 pb-4">
          <span className="font-mono text-[8px] tracking-[0.26em] text-carbon-soft">
            MV FACE RECOGNITION
          </span>
          <span className="font-kai text-[13px] font-bold text-carbon">後台 · 存根</span>
        </div>

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto">
          {sections.map((section) => (
            <div key={section.group} className="flex flex-col gap-1">
              <div className="flex flex-row items-baseline justify-between px-2 pb-1">
                <span className="font-kai text-[11px] text-carbon-soft">{section.group}</span>
                <span className="font-mono text-[7px] tracking-[0.18em] text-ledger">
                  {section.latin}
                </span>
              </div>
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `flex flex-row items-center justify-between border-l-[3px] px-2 py-1.5 ${
                      isActive
                        ? 'border-l-stamp bg-paper-light text-carbon-deep'
                        : 'border-l-transparent text-carbon-soft hover:bg-paper-light/60 hover:text-carbon'
                    }`
                  }
                >
                  <span className="font-kai text-[14px] font-bold">{item.label}</span>
                  <span className="font-mono text-[7px] tracking-[0.14em] opacity-70">
                    {item.latin}
                  </span>
                </NavLink>
              ))}
            </div>
          ))}
        </div>

        <div className="mt-4 flex flex-row items-center gap-2 border-t border-carbon/25 px-2 pt-3">
          <span
            className={`h-[7px] w-[7px] rounded-full ${
              status === 'online'
                ? 'bg-carbon'
                : status === 'offline'
                  ? 'bg-stamp'
                  : 'bg-ledger animate-pulse'
            }`}
          />
          <div className="flex flex-col">
            <span className="font-mono text-[8px] tracking-[0.14em] text-carbon">
              {status === 'online' ? 'LOCAL API ONLINE' : status === 'offline' ? 'API OFFLINE' : 'CHECKING'}
            </span>
            <span className="font-mono text-[7px] tracking-[0.1em] text-ledger">127.0.0.1:8000</span>
          </div>
        </div>
      </nav>

      <main className="flex min-w-0 flex-1 flex-col overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
