import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AdminLayout } from '@/layouts/AdminLayout';
import { Dashboard } from '@/pages/Dashboard';
import { Player } from '@/pages/Player';
import { EmbeddingWorkbench } from '@/pages/EmbeddingWorkbench';
import { Contestants } from '@/pages/Contestants';
import { Flagging } from '@/pages/Flagging';
import { Labelling } from '@/pages/Labelling';
import { Processing } from '@/pages/Processing';
import { Analytics } from '@/pages/Analytics';
import { SystemAdmin } from '@/pages/SystemAdmin';
import './app.css';

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
