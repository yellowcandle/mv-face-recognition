import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import {
  Card,
  Masthead,
  adminFetch,
  formatMmSs,
  useContestants,
  useFlaggedFaces,
  useVideos,
} from '@mv/shared';
import type { Contestant, FlaggedFace, Video } from '@mv/shared';

/** The processed-videos payload also carries reel dimensions; the shared type does not. */
type Reel = Video & {
  duration?: number;
  width?: number;
  height?: number;
};

interface SystemStatus {
  status?: string;
  mode?: string;
  chromadb_connected?: boolean;
  model_loaded?: boolean;
  services_running?: boolean;
  contestant_count?: number;
  video_count?: number;
  processing_jobs?: number;
}

interface LabelSummary {
  video_id: string;
  schema: string | null;
  count: number;
  labelled_at: string | null;
  legacy_ignored: boolean;
}

interface LabelsPayload {
  labels: LabelSummary[];
}

const LABELS_QUERY_KEY = ['labels'] as const;

function runtimeMode(status: SystemStatus | undefined): 'EDGE' | 'LOCAL' | '—' {
  if (!status) return '—';
  if (status.mode === 'edge') return 'EDGE';
  if (status.mode === 'local') return 'LOCAL';
  return status.chromadb_connected !== undefined ? 'EDGE' : 'LOCAL';
}

/** 管理 — the read model and the runbook, in one cabinet. */
export function SystemAdmin() {
  const statusQuery = useQuery<SystemStatus>({
    queryKey: ['system-status'],
    queryFn: async () => {
      const res = await fetch('/api/system/status');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return (await res.json()) as SystemStatus;
    },
    staleTime: 60 * 1000,
    retry: false,
  });

  const videosQuery = useVideos();
  const contestantsQuery = useContestants();
  const flagsQuery = useFlaggedFaces();

  // The Worker gates this behind Access; a 401/404 is an unavailable read model, not a crash.
  const labelsQuery = useQuery<LabelsPayload>({
    queryKey: LABELS_QUERY_KEY,
    queryFn: async () => {
      const res = await adminFetch('/admin/api/labels');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return (await res.json()) as LabelsPayload;
    },
    staleTime: 60 * 1000,
    retry: false,
  });

  const status = statusQuery.data;
  const reels = (videosQuery.data ?? []) as Reel[];
  const contestants = (contestantsQuery.data ?? []) as Contestant[];
  const flags = (flagsQuery.data ?? []) as FlaggedFace[];
  const labels = labelsQuery.data?.labels ?? [];

  const withEmbeddings = contestants.filter((c) => c.has_embedding).length;
  const pendingFlags = flags.filter((f) => f.status === 'pending').length;
  const labelsByVideo = new Map(labels.map((l) => [l.video_id, l]));

  const queryErrors = [
    statusQuery.error,
    videosQuery.error,
    contestantsQuery.error,
    flagsQuery.error,
    labelsQuery.error,
  ].filter((e): e is Error => e instanceof Error);

  function refreshAll() {
    void statusQuery.refetch();
    void videosQuery.refetch();
    void contestantsQuery.refetch();
    void flagsQuery.refetch();
    void labelsQuery.refetch();
  }

  const counters: { cn: string; latin: string; value: string }[] = [
    {
      cn: '運行環境',
      latin: 'RUNTIME',
      value: statusQuery.isError ? '—' : runtimeMode(status),
    },
    {
      cn: '已存影片',
      latin: 'REELS',
      value: videosQuery.isError ? '—' : String(reels.length),
    },
    {
      cn: '向量名冊',
      latin: 'CAST WITH EMBEDDINGS',
      value: contestantsQuery.isError ? '—' : `${withEmbeddings} / 96`,
    },
    {
      cn: '待核',
      latin: 'PENDING FLAGS',
      value: flagsQuery.isError ? '—' : String(pendingFlags),
    },
    {
      cn: '已標註影片',
      latin: 'LABELLED VIDEOS',
      value: labelsQuery.isError ? '—' : String(labels.length),
    },
  ];

  return (
    <div className="flex min-h-0 flex-1 flex-col px-9 pb-8 pt-7">
      <Masthead eyebrow="BACK OFFICE · SYSTEM" title="管理" latin="SYSTEM & READ MODEL" size="md">
        <button
          type="button"
          onClick={refreshAll}
          className="border border-carbon/45 px-3 py-1.5 font-kai text-[12px] tracking-[0.12em] text-carbon hover:border-stamp hover:text-stamp"
        >
          重新檢查
        </button>
      </Masthead>

      <div className="mt-4 h-px bg-carbon/45" />

      <div className="flex flex-row flex-wrap items-end gap-x-12 gap-y-4 py-4">
        {counters.map((c) => (
          <div key={c.latin} className="flex flex-col gap-1">
            <span className="font-mono text-[8px] tracking-[0.2em] text-ledger">{c.latin}</span>
            <span className="font-mono text-[22px] leading-none text-carbon">{c.value}</span>
            <span className="font-kai text-[11px] text-carbon-soft">{c.cn}</span>
          </div>
        ))}
      </div>

      <div className="h-px bg-carbon/20" />

      {queryErrors.length > 0 && (
        <div className="mt-4 border border-stamp/50 bg-stamp/10 px-4 py-2.5 font-kai text-[12px] text-stamp">
          {queryErrors.map((e, i) => (
            <div key={`${e.message}-${i}`}>{e.message}</div>
          ))}
        </div>
      )}

      <div className="mt-5 flex flex-row items-baseline justify-between">
        <h2 className="font-kai text-[15px] font-bold text-carbon">讀取模型 · 每卷影片</h2>
        <span className="font-mono text-[9px] tracking-[0.14em] text-ledger">
          {videosQuery.isLoading ? '調閱中…' : `${reels.length} REELS`}
        </span>
      </div>

      <div className="mt-2 overflow-x-auto border-y border-carbon/25">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-carbon/25">
              {['REEL', 'DURATION', 'DIMENSIONS', 'STREAM', 'LABELLED', ''].map((head) => (
                <th
                  key={head}
                  className="whitespace-nowrap py-2 pr-4 font-mono text-[8px] tracking-[0.16em] text-ledger"
                >
                  {head}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {reels.map((v) => {
              const labelled = labelsByVideo.get(v.id);
              return (
                <tr key={v.id} className="border-b border-carbon/15 align-top">
                  <td className="max-w-[360px] py-2.5 pr-4">
                    <div className="truncate font-kai text-[13px] text-carbon-deep" title={v.id}>
                      {v.id}
                    </div>
                    <div className="truncate font-mono text-[9px] tracking-[0.1em] text-ledger">
                      {v.name}
                    </div>
                  </td>
                  <td className="whitespace-nowrap py-2.5 pr-4 font-mono text-[11px] text-carbon-soft">
                    {typeof v.duration === 'number' && v.duration > 0
                      ? formatMmSs(v.duration)
                      : '—'}
                  </td>
                  <td className="whitespace-nowrap py-2.5 pr-4 font-mono text-[11px] text-carbon-soft">
                    {v.width && v.height ? `${v.width} × ${v.height}` : '—'}
                  </td>
                  <td className="max-w-[260px] py-2.5 pr-4">
                    <div
                      className="truncate font-mono text-[10px] text-carbon-soft"
                      title={v.stream_url}
                    >
                      {v.stream_url || '—'}
                    </div>
                  </td>
                  <td className="whitespace-nowrap py-2.5 pr-4 font-mono text-[11px] text-carbon-soft">
                    {labelsQuery.isError ? '—' : (labelled?.count ?? 0)}
                    {labelled?.legacy_ignored && (
                      <span className="ml-1 font-kai text-[9px] text-stamp">v1 ignored</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap py-2.5 font-kai text-[11px]">
                    <Link
                      to={`/player?video=${encodeURIComponent(v.id)}`}
                      className="text-stamp hover:text-carbon"
                    >
                      播放
                    </Link>
                    <span className="px-1.5 text-carbon/30">·</span>
                    <Link to="/labelling" className="text-stamp hover:text-carbon">
                      標註
                    </Link>
                  </td>
                </tr>
              );
            })}
            {!videosQuery.isLoading && reels.length === 0 && (
              <tr>
                <td colSpan={6} className="py-8 text-center font-kai text-[12px] text-carbon-soft">
                  還沒有可讀取的影片清單。
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="mt-6 flex flex-row gap-6">
        <Card padding="lg" className="flex-1">
          <h2 className="font-kai text-[15px] font-bold text-carbon">發佈與部署</h2>
          <p className="mt-1 font-kai text-[12px] text-carbon-soft">
            前端打包、讀取模型上傳與 Worker 部署，三個指令依序執行。
          </p>
          <ol className="mt-3 flex flex-col gap-1.5">
            {['npm run build', 'npm run publish:metadata:remote', 'npm run deploy'].map(
              (command, i) => (
                <li
                  key={command}
                  className="flex items-baseline gap-3 border-b border-carbon/15 pb-1.5 font-mono text-[12px] text-carbon-deep"
                >
                  <span className="w-4 shrink-0 text-[9px] text-ledger">0{i + 1}</span>
                  <code>{command}</code>
                </li>
              ),
            )}
          </ol>
        </Card>

        <Card padding="lg" className="w-[320px] shrink-0">
          <h2 className="font-kai text-[15px] font-bold text-carbon">讀取模型狀態</h2>
          <div className="mt-3 flex flex-col gap-2 font-mono text-[11px] text-carbon-soft">
            <div className="flex justify-between border-b border-carbon/15 pb-1.5">
              <span className="tracking-[0.12em] text-ledger">STATUS</span>
              <span className="text-carbon-deep">
                {statusQuery.isError ? '—' : (status?.status ?? '—')}
              </span>
            </div>
            <div className="flex justify-between border-b border-carbon/15 pb-1.5">
              <span className="tracking-[0.12em] text-ledger">MODEL</span>
              <span className="text-carbon-deep">
                {statusQuery.isError ? '—' : status?.model_loaded ? 'LOADED' : '—'}
              </span>
            </div>
            <div className="flex justify-between border-b border-carbon/15 pb-1.5">
              <span className="tracking-[0.12em] text-ledger">JOBS</span>
              <span className="text-carbon-deep">
                {statusQuery.isError ? '—' : (status?.processing_jobs ?? '—')}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="tracking-[0.12em] text-ledger">LABELS API</span>
              <span className="text-carbon-deep">
                {labelsQuery.isLoading ? '…' : labelsQuery.isError ? '—' : 'OK'}
              </span>
            </div>
          </div>
        </Card>
      </div>

      <div className="flex-1" />
      <div className="flex flex-row items-center justify-between border-t border-carbon/25 pt-3">
        <span className="font-mono text-[9px] tracking-[0.18em] text-ledger">
          WRITES ONLY ON THE LOCAL MACHINE
        </span>
        <span className="font-kai text-[11px] text-carbon-soft">存根 · 唯讀檢查</span>
      </div>
    </div>
  );
}
