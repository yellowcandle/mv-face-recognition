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
import { Ingestion } from '@/pages/Ingestion';
import { Processing } from '@/pages/Processing';
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
      <BrowserRouter>
        <Routes>
          <Route element={<AdminLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="player" element={<Player />} />
            <Route path="contestants" element={<Contestants />} />
            <Route path="ingestion" element={<Ingestion />} />
            <Route path="analytics" element={<div className="text-slate-400">Analytics — coming soon</div>} />
            <Route path="flagging" element={<Flagging />} />
            <Route path="processing" element={<Processing />} />
            <Route path="embedding-workbench" element={<EmbeddingWorkbench />} />
            <Route path="admin" element={<div className="text-slate-400">Admin — coming soon</div>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>
);
