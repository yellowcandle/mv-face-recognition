import { Outlet, NavLink } from 'react-router';

/**
 * The spine is the route rail: the slip's folios. 01 圖庫 · 02 播放 · 03 名冊 · 04 紀錄.
 * One punched strip, no top navigation bar — the form owns the frame.
 */
const folios = [
  { to: '/', no: '01', label: '圖庫', latin: 'LIBRARY' },
  { to: '/player', no: '02', label: '播放', latin: 'PLAYER' },
  { to: '/cast', no: '03', label: '名冊', latin: 'CAST' },
  { to: '/analytics', no: '04', label: '紀錄', latin: 'LEDGER' },
];

export function ViewerLayout() {
  return (
    <div className="flex h-full flex-row bg-paper">
      <nav className="flex w-[76px] shrink-0 flex-col items-center justify-between border-r border-carbon/30 bg-paper-dark py-8">
        <div className="flex flex-col items-center gap-6">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-[22px] w-[22px] rounded-full border border-carbon/35 bg-paper-deep shadow-[inset_0_1px_2px_rgba(43,47,107,0.25)]"
            />
          ))}
        </div>

        <div className="flex flex-col items-center gap-7">
          {folios.map((f) => (
            <NavLink
              key={f.to}
              to={f.to}
              end={f.to === '/'}
              className={({ isActive }) =>
                `group flex w-full flex-col items-center gap-1 ${isActive ? '' : 'opacity-70 hover:opacity-100'}`
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={`font-mono text-[19px] leading-none tracking-tight ${
                      isActive ? 'text-stamp' : 'text-carbon'
                    }`}
                  >
                    {f.no}
                  </span>
                  <span
                    className={`font-kai text-[12px] leading-none ${
                      isActive ? 'text-carbon-deep' : 'text-carbon-soft'
                    }`}
                  >
                    {f.label}
                  </span>
                  <span
                    className={`mt-1 h-[3px] w-4 ${isActive ? 'bg-stamp' : 'bg-transparent'}`}
                  />
                </>
              )}
            </NavLink>
          ))}
        </div>

        <div className="font-mono text-[9px] tracking-[0.22em] text-carbon-soft">MVFR</div>
      </nav>

      <main className="flex min-w-0 flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  );
}
