import { Link } from 'react-router';
import { useQuery } from '@tanstack/react-query';
import {
  Button,
  Masthead,
  adminFetch,
  formatMmSs,
  useContestants,
  useFlaggedFaces,
  useVideos,
  videoShortName,
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

  const counters: { label: string; value: string }[] = [
    { label: '運行環境', value: statusQuery.isError ? '—' : runtimeMode(status) },
    { label: '已存影片', value: videosQuery.isError ? '—' : String(reels.length) },
    {
      label: '向量名冊',
      value: contestantsQuery.isError ? '—' : `${withEmbeddings} / ${contestants.length}`,
    },
    { label: '待核', value: flagsQuery.isError ? '—' : String(pendingFlags) },
    { label: '已標註影片', value: labelsQuery.isError ? '—' : String(labels.length) },
  ];

  const statusRows: { label: string; value: string | number }[] = [
    { label: '狀態', value: statusQuery.isError ? '—' : (status?.status ?? '—') },
    { label: '模型', value: statusQuery.isError ? '—' : status?.model_loaded ? 'LOADED' : '—' },
    { label: '工作', value: statusQuery.isError ? '—' : (status?.processing_jobs ?? '—') },
    { label: '標註 API', value: labelsQuery.isLoading ? '…' : labelsQuery.isError ? '—' : 'OK' },
  ];

  return (
    <div className="flex min-h-full flex-1 flex-col gap-6 px-8 pb-5 pt-8">
      <Masthead title="管理" hint="服務狀態與資料檢查">
        <Button onClick={refreshAll}>重新檢查</Button>
      </Masthead>

      <div className="flex flex-row border-y border-carbon-deep/13 py-4">
        {counters.map((c) => (
          <div key={c.label} className="flex flex-1 flex-col gap-1">
            <span className="font-kai text-[13px] text-carbon-soft">{c.label}</span>
            <span className="font-mono text-[28px] leading-[1.15] tabular-nums text-carbon-deep">
              {c.value}
            </span>
          </div>
        ))}
      </div>

      {queryErrors.length > 0 && (
        <div role="alert" className="border-y border-stamp/33 py-2 font-kai text-[13px] text-stamp">
          {queryErrors.map((e, i) => (
            <div key={`${e.message}-${i}`}>{e.message}</div>
          ))}
        </div>
      )}

      <section className="flex flex-col gap-2">
        <div className="flex flex-row items-end justify-between">
          <h2 className="font-kai text-[18px] font-normal text-carbon-deep">讀取模型 · 每卷影片</h2>
          {videosQuery.isLoading ? (
            <span className="font-kai text-[12px] text-ink-muted">調閱中…</span>
          ) : (
            <span className="font-mono text-[12px] tabular-nums text-ink-muted">
              {reels.length} 卷
            </span>
          )}
        </div>

        <table className="w-full table-fixed border-collapse text-left">
          <thead>
            <tr className="h-7 border-b border-carbon-deep/33 font-kai text-[12px] text-ink-muted">
              <th className="w-[264px] pr-4 font-normal">影片</th>
              <th className="w-[100px] pr-4 font-normal">長度</th>
              <th className="w-[128px] pr-4 font-normal">尺寸</th>
              <th className="pr-4 font-normal">串流</th>
              <th className="w-[108px] pr-4 text-right font-normal">已標註</th>
              <th className="w-[84px] font-normal">
                <span className="sr-only">操作</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {reels.map((v) => {
              const labelled = labelsByVideo.get(v.id);
              return (
                <tr key={v.id} className="h-12 border-b border-carbon-deep/13 [&>td]:pt-2">
                  <td
                    className="truncate pr-4 font-kai text-[15px] text-carbon-deep"
                    title={v.name}
                  >
                    {videoShortName(v.name)}
                  </td>
                  <td className="pr-4 font-mono text-[12px] tabular-nums text-carbon-soft">
                    {typeof v.duration === 'number' && v.duration > 0
                      ? formatMmSs(v.duration)
                      : '—'}
                  </td>
                  <td className="whitespace-nowrap pr-4 font-mono text-[12px] tabular-nums text-carbon-soft">
                    {v.width && v.height ? `${v.width} × ${v.height}` : '—'}
                  </td>
                  <td
                    className="truncate pr-4 font-mono text-[12px] text-carbon-soft"
                    title={v.stream_url}
                  >
                    {v.stream_url || '—'}
                  </td>
                  <td className="whitespace-nowrap pr-4 text-right font-mono text-[12px] tabular-nums text-carbon-soft">
                    {labelled?.legacy_ignored && (
                      <span className="mr-1.5 font-kai text-ink-muted">略過 v1</span>
                    )}
                    {labelsQuery.isError ? '—' : (labelled?.count ?? 0)}
                  </td>
                  <td className="whitespace-nowrap text-right font-kai text-[13px]">
                    <Link
                      to={`/player?video=${encodeURIComponent(v.id)}`}
                      className="text-stamp hover:underline"
                    >
                      播放
                    </Link>
                    <Link to="/labelling" className="ml-2 text-stamp hover:underline">
                      標註
                    </Link>
                  </td>
                </tr>
              );
            })}
            {!videosQuery.isLoading && reels.length === 0 && (
              <tr>
                <td colSpan={6} className="py-8 text-center font-kai text-[13px] text-carbon-soft">
                  還沒有可讀取的影片清單。
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      <div className="flex flex-row gap-10">
        <section className="flex min-w-0 flex-1 flex-col gap-2">
          <h2 className="font-kai text-[18px] font-normal text-carbon-deep">發佈與部署</h2>
          <p className="font-kai text-[14px] text-carbon-soft">
            前端打包、讀取模型上傳與 Worker 部署，三個指令依序執行
          </p>
          <ol className="flex flex-col">
            {['npm run build', 'npm run publish:metadata:remote', 'npm run deploy'].map(
              (command, i) => (
                <li
                  key={command}
                  className="flex h-7 flex-row items-center gap-3 border-b border-carbon-deep/13 font-mono text-[13px]"
                >
                  <span className="text-[12px] tabular-nums text-ink-muted">0{i + 1}</span>
                  <code className="text-carbon-deep">{command}</code>
                </li>
              ),
            )}
          </ol>
        </section>

        <section className="flex w-[360px] shrink-0 flex-col gap-2">
          <h2 className="font-kai text-[18px] font-normal text-carbon-deep">讀取模型狀態</h2>
          <dl className="flex flex-col">
            {statusRows.map((row) => (
              <div
                key={row.label}
                className="flex h-7 flex-row items-center justify-between border-b border-carbon-deep/13"
              >
                <dt className="font-kai text-[13px] text-carbon-soft">{row.label}</dt>
                <dd className="font-mono text-[12px] tabular-nums text-carbon-deep">{row.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>

      <div className="flex-1" />
      <div className="flex flex-row items-center justify-between font-kai text-[12px] text-ink-muted">
        <span>所有寫入只在這一台機器上發生</span>
        <span>存根 · 唯讀檢查</span>
      </div>
    </div>
  );
}
