import { Outlet, NavLink } from 'react-router';

const navItems = [
  { to: '/', label: 'Home' },
  { to: '/player', label: 'Video Player' },
  { to: '/analytics', label: 'Analytics' },
];

export function ViewerLayout() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="h-14 flex items-center justify-between px-6 border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm">
        <NavLink to="/" className="text-lg font-semibold text-slate-100">
          MV Face Recognition
        </NavLink>
        <nav className="flex gap-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `px-4 py-2 rounded-full text-sm transition-colors ${
                  isActive
                    ? 'bg-orange-600 text-white font-semibold'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
