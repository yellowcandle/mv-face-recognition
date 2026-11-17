import { StrictMode, lazy } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AdminLayout } from '@/layouts/AdminLayout';
import { Dashboard } from '@/pages/Dashboard';
import './app.css';

// Every route except the landing Dashboard is code-split so the entry chunk stays small.
const Player = lazy(() => import('@/pages/Player').then((m) => ({ default: m.Player })));
const EmbeddingWorkbench = lazy(() =>
  import('@/pages/EmbeddingWorkbench').then((m) => ({ default: m.EmbeddingWorkbench })),
);
const Contestants = lazy(() => import('@/pages/Contestants').then((m) => ({ default: m.Contestants })));
const Flagging = lazy(() => import('@/pages/Flagging').then((m) => ({ default: m.Flagging })));
const Labelling = lazy(() => import('@/pages/Labelling').then((m) => ({ default: m.Labelling })));
const Processing = lazy(() => import('@/pages/Processing').then((m) => ({ default: m.Processing })));
const Analytics = lazy(() => import('@/pages/Analytics').then((m) => ({ default: m.Analytics })));
const SystemAdmin = lazy(() => import('@/pages/SystemAdmin').then((m) => ({ default: m.SystemAdmin })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 10 * 60 * 1000,
    },
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename="/admin">
        <Routes>
          <Route element={<AdminLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="player" element={<Player />} />
            <Route path="contestants" element={<Contestants />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="flagging" element={<Flagging />} />
            <Route path="labelling" element={<Labelling />} />
            <Route path="processing" element={<Processing />} />
            <Route path="embedding-workbench" element={<EmbeddingWorkbench />} />
            <Route path="admin" element={<SystemAdmin />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
