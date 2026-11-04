import { useMemo } from 'react';
import { Link } from 'react-router';
import {
  AdminErrorNotice,
  Masthead,
  formatMmSs,
  useContestants,
  useCoverage,
  useFlaggedFaces,
  useVideos,
} from '@mv/shared';
import type { FlaggedFace } from '@mv/shared';

/** The flag API stamps each record with `created_at`; the shared type predates that field. */
type DatedFlag = FlaggedFace & { created_at?: string };

function createdMs(flag: FlaggedFace): number {
  const iso = (flag as DatedFlag).created_at;
  const ms = iso ? Date.parse(iso) : NaN;
  return Number.isNaN(ms) ? -Infinity : ms;
}

/** 儀表 — the operator's desk: coverage, what is waiting, and the faces just filed. */
export function Dashboard() {
  const { data: videos = [] } = useVideos();
  const { data: roster } = useContestants();
  const { data: coverage } = useCoverage();
  const {
    data: flagged = [],
    error: flagsError,
    isLoading: flagsLoading,
    refetch: refetchFlags,
  } = useFlaggedFaces();

  const summary = coverage?.summary;
  const pending = flagged.filter((f) => f.status === 'pending').length;
  const accepted = flagged.filter((f) => f.status === 'accepted').length;

  // The preview is a queue, not an archive: only pending slips, newest first.
  const recentPending = useMemo(
    () =>
      flagged
        .map((flag, index) => ({ flag, index }))
        .filter(({ flag }) => flag.status === 'pending')
        .sort((a, b) => createdMs(b.flag) - createdMs(a.flag) || a.index - b.index)
        .slice(0, 6)
        .map(({ flag }) => flag),
    [flagged],
  );

  // The faces most recently filed: the product's own content on the desk.
  const recentAccepted = useMemo(
    () =>
      flagged
        .map((flag, index) => ({ flag, index }))
        .filter(({ flag }) => flag.status === 'accepted')
        .sort((a, b) => createdMs(b.flag) - createdMs(a.flag) || a.index - b.index)
        .slice(0, 4)
        .map(({ flag }) => flag),
    [flagged],
  );

  const total = summary?.total ?? 0;

  const counters: { cn: string; latin: string; value: string | number }[] = [
    { cn: '已存影片', latin: 'REELS', value: videos.length },
    { cn: '參賽者', latin: 'CAST', value: roster ? roster.length : '—' },
    { cn: '待核', latin: 'PENDING', value: pending },
    { cn: '已核對', latin: 'ACCEPTED', value: accepted },
  ];

  const coverageBands = [
    { key: 'good', label: '齊全', value: summary?.good ?? 0, className: 'bg-carbon' },
    { key: 'weak', label: '偏弱', value: summary?.weak ?? 0, className: 'bg-stamp' },
    {
      key: 'missing',
      label: '缺',
      value: summary?.missing ?? 0,
      className: 'border border-ledger bg-paper-deep',
    },
  ];

  return (
    <div className="flex min-h-0 flex-1 flex-col px-9 pb-6 pt-7">
      <Masthead eyebrow="BACK OFFICE · LOCAL ONLY · 127.0.0.1" title="儀表" latin="DESK" size="md">
        所有寫入只在這一台機器上發生
      </Masthead>

      <div className="mt-4 h-px bg-carbon/45" />

      {flagsError ? (
        <AdminErrorNotice error={flagsError} onRetry={() => void refetchFlags()} className="mt-3" />
      ) : null}

      {/* 名冊覆蓋 — the one rich moment: 96 contestants, three bands. */}
      <section className="mt-5 flex flex-col gap-2">
        <div className="flex flex-row items-end justify-between">
          <span className="font-mono text-[11px] tracking-[0.22em] text-ledger">
            名冊覆蓋 · ROSTER COVERAGE
          </span>
          <div className="flex flex-row items-end gap-1.5">
            <span className="font-mono text-[26px] leading-none text-stamp">
              {summary ? summary.good : '—'}
            </span>
            <span className="px-0.5 font-kai text-[12px] leading-none text-carbon-soft">
              / {summary ? summary.total : '—'} 齊全
            </span>
          </div>
        </div>

        <div
          className="flex h-3 w-full flex-row gap-0.5"
          role="img"
          aria-label={
            summary
              ? `名冊覆蓋：齊全 ${summary.good}、偏弱 ${summary.weak}、缺 ${summary.missing}，共 ${summary.total}`
              : '名冊覆蓋載入中'
          }
        >
          {coverageBands.map((band) => (
            <div
              key={band.key}
              className={`h-3 ${band.className}`}
              style={{ width: `${total > 0 ? (band.value / total) * 100 : 0}%` }}
            />
          ))}
        </div>

        <div className="flex flex-row gap-6">
          {coverageBands.map((band) => (
            <span
              key={band.key}
              className="flex flex-row items-center gap-2 font-mono text-[11px] tracking-[0.1em] text-carbon-soft"
            >
              <span aria-hidden className={`h-2.5 w-2.5 ${band.className}`} />
              {band.label} {summary ? band.value : '—'}
            </span>
          ))}
        </div>
      </section>

      <div className="mt-4 h-px bg-carbon/25" />

      {/* Ledger strip — numbers only, one cell each. */}
      <div className="mt-4 flex flex-row">
        {counters.map((c, i) => (
          <div
            key={c.latin}
            className={`flex flex-1 flex-col gap-1 px-5 ${i > 0 ? 'border-l border-carbon/25' : ''}`}
          >
            <span className="font-mono text-[11px] tracking-[0.18em] text-ledger">
              {c.cn} {c.latin}
            </span>
            <span className="font-mono text-[28px] leading-none text-carbon">{c.value}</span>
          </div>
        ))}
      </div>

      <div className="mt-4 flex min-h-0 flex-1 flex-row gap-8">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex flex-row items-baseline justify-between pb-2">
            <span className="font-kai text-[15px] font-bold text-carbon">待核紀錄</span>
            <Link to="/flagging" className="font-mono text-[11px] tracking-[0.14em] text-stamp">
              前往托盤 →
            </Link>
          </div>
          <div className="h-px bg-carbon/25" />

          {flagsLoading ? (
            <div className="mt-2 flex flex-1 items-center justify-center border border-carbon/20 font-kai text-[12px] text-carbon-soft">
              正在調閱待核紀錄…
            </div>
          ) : recentPending.length === 0 ? (
            <div className="mt-2 flex flex-1 flex-col items-center justify-center gap-2 border border-carbon/25">
              <span className="font-serif text-[38px] font-black leading-none text-carbon-deep">
                0
              </span>
              <span className="font-kai text-[14px] font-bold text-carbon-deep">待核清空</span>
              <span className="font-kai text-[12px] text-carbon-soft">新的標記會出現在這裡</span>
            </div>
          ) : (
            <div className="flex flex-col pt-1">
              {recentPending.map((f) => (
                <div
                  key={f.id}
                  className="flex flex-row items-center gap-3 border-b border-carbon/15 py-2"
                >
                  <div className="h-10 w-10 shrink-0 overflow-hidden border border-carbon/40 bg-paper-dark">
                    {f.thumbnail ? (
                      <img
                        src={f.thumbnail}
                        alt={`待核 #${f.contestant_id}`}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center font-mono text-[7px] tracking-[0.1em] text-ledger">
                        NO FACE
                      </div>
                    )}
                  </div>
                  <span className="w-[46px] font-mono text-[11px] text-carbon-soft">
                    {formatMmSs(f.timestamp)}
                  </span>
                  <span className="flex-1 truncate font-kai text-[14px] font-bold text-carbon-deep">
                    #{f.contestant_id}
                  </span>
                  <span className="font-mono text-[9px] tracking-[0.12em] text-ledger">
                    {f.video_id}
                  </span>
                  <span className="-rotate-2 border border-stamp px-1.5 py-0.5 font-kai text-[10px] text-stamp">
                    待核
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex w-[320px] shrink-0 flex-col gap-2">
          <div className="flex flex-row items-baseline justify-between pb-2">
            <span className="font-kai text-[15px] font-bold text-carbon">最近核對</span>
            <span className="font-mono text-[11px] tracking-[0.18em] text-ledger">RECENT</span>
          </div>
          <div className="h-px bg-carbon/25" />

          {recentAccepted.length === 0 ? (
            <div className="flex h-24 items-center justify-center border border-carbon/20 font-kai text-[12px] text-carbon-soft">
              尚無已核對的人臉
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              {recentAccepted.map((f) => (
                <Link key={f.id} to="/flagging" className="group flex flex-col gap-1">
                  <div className="relative aspect-square overflow-hidden border border-carbon/30 bg-paper-dark">
                    {f.thumbnail ? (
                      <img
                        src={f.thumbnail}
                        alt={`已核對 #${f.contestant_id}`}
                        loading="lazy"
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center font-kai text-[11px] tracking-[0.12em] text-ledger">
                        無縮圖
                      </div>
                    )}
                  </div>
                  <div className="flex flex-row items-baseline justify-between">
                    <span className="font-mono text-[11px] text-carbon-soft">
                      #{f.contestant_id}
                    </span>
                    <span className="font-mono text-[11px] text-ledger">
                      {formatMmSs(f.timestamp)}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 flex flex-row items-center justify-between border-t border-carbon/25 pt-3">
        <span className="font-mono text-[11px] tracking-[0.18em] text-ledger">
          分級為暫定值，依實測誤配率調整
        </span>
        <span className="font-kai text-[11px] text-carbon-soft">存根 · 可寫</span>
      </div>
    </div>
  );
}
