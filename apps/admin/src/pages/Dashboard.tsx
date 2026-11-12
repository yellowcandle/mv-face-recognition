import { Link } from 'react-router';
import {
  AdminErrorNotice,
  Masthead,
  Stamp,
  bandFor,
  formatMmSs,
  recentDecisions,
  reelSummary,
  useContestants,
  useCoverage,
  useFlaggedFaces,
  useVideos,
  videoShortName,
} from '@mv/shared';
import { QUALITY_WORD } from '@mv/shared/lib/pipeline';
import type { Contestant } from '@mv/shared';
import { useIsEdge } from '../useIsEdge';

const QUALITY_FILL: Record<Contestant['quality'], string> = {
  good: 'bg-carbon',
  // Muted like the other weak swatches, lightened so it separates from navy in the thin strip.
  weak: 'bg-ink-muted/40',
  missing: 'bg-stamp',
};

const SHORTCUTS = [
  { to: '/flagging', label: '待核托盤' },
  { to: '/contestants', label: '參賽者名冊' },
  { to: '/player', label: '播放與校正' },
  { to: '/embedding-workbench', label: '向量工作台' },
  { to: '/processing', label: '處理進度' },
];

/** 儀表 — the operator's desk: what is filed, what is waiting, where to go. */
export function Dashboard() {
  const isEdge = useIsEdge();
  const { data: videos = [] } = useVideos('', { includeTests: true });
  const {
    data: flagged = [],
    error: flaggedError,
    isLoading: flaggedLoading,
    refetch: refetchFlagged,
  } = useFlaggedFaces();
  const { data: contestants = [] } = useContestants();
  const { data: coverage, error: coverageError } = useCoverage();

  const summary = coverage?.summary;
  const roster = [...(coverage?.contestants ?? [])].sort((a, b) => Number(a.id) - Number(b.id));
  const missing = roster.filter((c) => c.quality === 'missing');

  const pending = flagged.filter((f) => f.status === 'pending');
  const accepted = flagged.filter((f) => f.status === 'accepted').length;
  const recent = recentDecisions(flagged);
  // The preview is a queue, not an archive: pending slips only, newest first.
  const recentPending = [...pending]
    .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''))
    .slice(0, 6);

  const contestantOf = (id: number) =>
    (contestants as Contestant[]).find((c) => Number(c.id) === Number(id));

  const stats = [
    { label: '已存影片', value: videos.length, note: reelSummary(videos.map((v) => v.id)) },
    { label: '已核對', value: accepted, note: '本機人工確認' },
    {
      label: '辨識率',
      value: summary ? `${(summary.recognition_rate * 100).toFixed(1)}%` : '—',
      note: summary
        ? `${summary.total_faces_recognized.toLocaleString('en-US')} / ${summary.total_faces_detected.toLocaleString('en-US')} 張臉`
        : '—',
    },
    {
      label: '平均配對分數',
      value: summary ? summary.avg_match_score.toFixed(2) : '—',
      note: '分級暫定',
    },
  ];

  return (
    <div className="flex min-h-full flex-1 flex-col gap-6 px-4 pb-5 pt-8 sm:px-8">
      <Masthead title="儀表" hint="待辦、數量與捷徑總覽">
        {isEdge === false && '所有寫入只在這一台機器上發生'}
      </Masthead>

      <section className="flex flex-col gap-3">
        <div className="flex flex-row flex-wrap items-end justify-between gap-x-6 gap-y-2">
          <div className="flex flex-row items-end gap-2">
            <span className="font-mono text-[32px] leading-tight tabular-nums text-carbon-deep">
              {summary?.good ?? '—'}
            </span>
            <span className="font-kai text-[14px] text-carbon-soft">
              / {summary?.total ?? '—'} 位參賽者參考相齊全
            </span>
          </div>
          {summary ? (
            <div className="flex flex-row flex-wrap items-center gap-x-4 gap-y-1 font-kai text-[13px] text-carbon-soft">
              <LegendKey fill={QUALITY_FILL.good}>
                {QUALITY_WORD.good} {summary.good}
              </LegendKey>
              <LegendKey fill={QUALITY_FILL.weak}>
                {QUALITY_WORD.weak} {summary.weak}
              </LegendKey>
              <LegendKey fill={QUALITY_FILL.missing}>
                {QUALITY_WORD.missing} {summary.missing}
                {missing.length > 0
                  ? ` · ${missing.map((c) => `${c.nickname} #${c.id}`).join('、')}`
                  : ''}
              </LegendKey>
            </div>
          ) : null}
        </div>
        {coverageError ? (
          <div className="font-kai text-[13px] text-stamp">
            讀不到參考相覆蓋率 — 後台 API 未啟動？
          </div>
        ) : (
          <div
            role="img"
            aria-label={
              summary
                ? `參考相齊全 ${summary.good}、偏弱 ${summary.weak}、缺 ${summary.missing}`
                : '參考相覆蓋率'
            }
            className="flex h-7 flex-row gap-0.5 max-sm:grid max-sm:h-auto max-sm:grid-cols-[repeat(48,minmax(0,1fr))] max-sm:gap-px"
          >
            {roster.map((c) => (
              <span
                key={c.id}
                title={`#${c.id} ${c.nickname} · ${QUALITY_WORD[c.quality]}`}
                className={`min-w-0 flex-1 max-sm:h-7 ${QUALITY_FILL[c.quality]}`}
              />
            ))}
          </div>
        )}
      </section>

      <section className="flex flex-row border-y border-carbon-deep/13 py-4 max-sm:grid max-sm:grid-cols-2 max-sm:gap-y-3">
        {stats.map((s) => (
          <div key={s.label} className="flex min-w-0 flex-1 flex-col gap-1">
            <span className="font-kai text-[13px] text-carbon-soft">{s.label}</span>
            <span className="font-mono text-[28px] leading-tight tabular-nums text-carbon-deep">
              {s.value}
            </span>
            <span className="font-kai text-[12px] text-ink-muted">{s.note}</span>
          </div>
        ))}
      </section>

      <div className="flex flex-1 flex-row gap-10 max-lg:flex-col">
        <section className="flex min-w-0 flex-1 flex-col">
          <div className="flex flex-row items-center justify-between pb-2">
            <div className="flex flex-row items-end gap-2 text-[18px]">
              <h2 className="font-kai font-normal text-carbon-deep">待核紀錄</h2>
              <span className="font-mono tabular-nums text-stamp">{pending.length}</span>
            </div>
            <Link
              to="/flagging"
              className="rounded-md font-kai text-[14px] text-stamp hover:underline max-sm:py-3"
            >
              前往待核 →
            </Link>
          </div>
          {flaggedError ? (
            <AdminErrorNotice error={flaggedError} onRetry={() => void refetchFlagged()} />
          ) : flaggedLoading ? (
            <div className="border-t border-carbon-deep/13 py-10 text-center font-kai text-[13px] text-carbon-soft">
              正在調閱待核紀錄…
            </div>
          ) : recentPending.length === 0 ? (
            <div className="border-t border-carbon-deep/13 py-10 text-center font-kai text-[13px] text-carbon-soft">
              目前沒有待核的人臉標記。
            </div>
          ) : (
            recentPending.map((f) => {
              const c = contestantOf(f.contestant_id);
              return (
                <div
                  key={f.id}
                  className="flex h-15 shrink-0 flex-row items-center gap-3 border-t border-carbon-deep/13"
                >
                  <div className="h-11 w-11 shrink-0 overflow-hidden rounded bg-tint">
                    {f.thumbnail ? (
                      <img
                        src={f.thumbnail}
                        alt={`待核 ${c?.nickname ?? `#${f.contestant_id}`}`}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center font-kai text-[12px] text-ink-muted">
                        無相
                      </div>
                    )}
                  </div>
                  <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <div className="flex flex-row items-baseline gap-2">
                      <span className="truncate font-kai text-[15px] text-carbon-deep">
                        {c?.nickname ?? `#${f.contestant_id}`}
                      </span>
                      <span className="shrink-0 font-kai text-[12px] text-ink-muted">
                        {c?.name} #{f.contestant_id}
                      </span>
                    </div>
                    <span className="truncate font-mono text-[12px] text-ink-muted">
                      {formatMmSs(f.timestamp)} · {videoShortName(f.video_id)}
                    </span>
                  </div>
                  <span className="font-mono text-[14px] tabular-nums text-carbon-deep">
                    {f.confidence == null ? '—' : f.confidence.toFixed(2)}
                  </span>
                  <Stamp band={bandFor(f.confidence)} />
                </div>
              );
            })
          )}
        </section>

        <div className="flex w-[360px] shrink-0 flex-col gap-3 max-lg:w-full">
          <div className="flex h-7 flex-row items-baseline justify-between">
            <h2 className="font-kai text-[18px] font-normal text-carbon-deep">最近核對</h2>
            <span className="font-kai text-[12px] text-ink-muted">依標記時間排序</span>
          </div>
          {recent.length === 0 ? (
            <div className="border-t border-carbon-deep/13 py-10 text-center font-kai text-[13px] text-carbon-soft">
              尚未核對任何標記。
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3">
              {recent.map((f) => (
                <div key={f.id} className="flex min-w-0 flex-col gap-1">
                  <div className="relative h-32 overflow-hidden rounded bg-tint">
                    {f.thumbnail ? (
                      <img src={f.thumbnail} alt="" className="h-full w-full object-cover" />
                    ) : null}
                    <Stamp tilt className="absolute bottom-2.5 right-4">
                      已核對
                    </Stamp>
                  </div>
                  <span className="truncate font-kai text-[13px] text-carbon">
                    {contestantOf(f.contestant_id)?.nickname ?? `#${f.contestant_id}`}
                  </span>
                </div>
              ))}
            </div>
          )}
          <nav
            aria-label="捷徑"
            className="mt-auto flex flex-row flex-wrap gap-x-3 gap-y-1 border-t border-carbon-deep/13 pt-3 font-kai text-[13px]"
          >
            {SHORTCUTS.map((l) => (
              <Link
                key={l.to}
                to={l.to}
                className="rounded-md text-carbon-soft hover:text-stamp max-sm:py-3"
              >
                {l.label}
              </Link>
            ))}
          </nav>
        </div>
      </div>

      <div className="flex flex-row flex-wrap justify-between gap-x-4 gap-y-1 font-kai text-[12px] text-ink-muted">
        <span>分級為暫定值，依實測誤配率調整</span>
        <span>存根 · 可寫</span>
      </div>
    </div>
  );
}

function LegendKey({ fill, children }: { fill: string; children: React.ReactNode }) {
  return (
    <span className="flex flex-row items-center gap-1.5">
      <span className={`h-2.5 w-2.5 shrink-0 ${fill}`} />
      {children}
    </span>
  );
}
