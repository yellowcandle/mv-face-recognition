import { NavLink, Outlet } from 'react-router';

const NAV = [
  { to: '/', label: '首頁', hint: '選片入口 · 點唱單', latin: 'HOME' },
  { to: '/player', label: '播放', hint: '看片、人臉框與時間軸', latin: 'PLAYER' },
  { to: '/analytics', label: '紀錄', hint: '唯讀的辨識結果帳冊', latin: 'LEDGER' },
  { to: '/cast', label: '名冊', hint: '參賽者、參考照與出場次數', latin: 'CAST' },
];

/**
 * One printed slip, read page by page: a hairline index across the top, the folio below.
 * The old punched spine took 76px of every page for four links.
 */
export function ViewerLayout() {
  return (
    <div className="flex h-full flex-col bg-paper">
      <header className="flex shrink-0 flex-row items-center justify-between border-b border-carbon/30 px-14 py-3">
        <span className="font-mono text-[9px] tracking-[0.3em] text-carbon-soft">MVFR</span>
        <nav className="flex flex-row items-center gap-8">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex flex-col gap-0.5 ${isActive ? '' : 'opacity-60 hover:opacity-100'}`
              }
            >
              {({ isActive }) => (
                <>
                  <span className="flex flex-row items-baseline gap-2">
                    <span
                      className={`font-serif text-[13px] font-bold ${
                        isActive ? 'text-carbon-deep' : 'text-ledger'
                      }`}
                    >
                      {item.label}
                    </span>
                    <span
                      className={`font-mono text-[8px] tracking-[0.22em] ${
                        isActive ? 'text-stamp' : 'text-ledger'
                      }`}
                    >
                      {item.latin}
                    </span>
                  </span>
                  <span className="font-kai text-[9px] leading-none text-ledger">{item.hint}</span>
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
