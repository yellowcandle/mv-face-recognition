import { Link } from 'react-router';
import {
  Badge,
  Masthead,
  Stamp,
  bandFor,
  contestantsSeen,
  formatMmSs,
  mostSeen,
  reelRange,
  reelSubtitle,
  renditionLabel,
  useCoverage,
  useVideos,
  videoShortName,
} from '@mv/shared';
import type { Video } from '@mv/shared';

/** The list route also sends these; `Video` doesn't declare them. */
type FiledVideo = Video & { duration?: number; height?: number };

/**
 * 點唱單 — the request slip. The reels filed on the left, the current tally on the right,
 * and the faces that keep returning along the foot of the page.
 */
export function Home() {
  const { data, isLoading } = useVideos();
  const { data: coverage } = useCoverage();

  const videos: FiledVideo[] = data ?? [];
  const summary = coverage?.summary;
  const contestants = coverage?.contestants ?? [];
  const regulars = mostSeen(contestants, 4);

  const tally = [
    ['平均配對分數', summary ? summary.avg_match_score.toFixed(2) : '—'],
    ['出場參賽者', coverage ? `${contestantsSeen(contestants)} 位` : '—'],
    ['辨識率', summary ? `${(summary.recognition_rate * 100).toFixed(1)}%` : '—'],
  ];

  return (
    <div className="flex min-h-full flex-1 flex-col gap-6 px-14 pb-5 pt-8">
      <Masthead title="點唱單" hint="選片入口 · 點唱單" />

      <div className="flex flex-row gap-14">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex flex-row items-end justify-between border-b border-carbon-deep/33 pb-3 font-kai text-[13px] leading-tight tabular-nums text-carbon-soft">
            <span>{isLoading ? '—' : reelRange(videos.length)}</span>
            <span>
              {summary
                ? `${summary.total} 位 · ${summary.total_faces_recognized.toLocaleString('en-US')} 辨識`
                : '—'}
            </span>
          </div>

          {isLoading ? (
            <div className="py-16 text-center font-kai text-[13px] text-ink-muted">正在調閱…</div>
          ) : videos.length === 0 ? (
            <div className="border-b border-carbon-deep/13 px-4 py-14 text-center">
              <div className="font-kai text-[15px] text-carbon-deep">尚未有已處理影片</div>
              <div className="mt-1 font-kai text-[13px] text-ink-muted">
                處理完成的影片會存進這裡。
              </div>
            </div>
          ) : (
            videos.map((video, index) => {
              const subtitle = reelSubtitle(video.name);
              const rendition = renditionLabel(video.height);
              return (
                <Link
                  key={video.id}
                  to={`/player?video=${encodeURIComponent(video.id)}`}
                  className="flex h-[72px] flex-row items-center gap-4 border-b border-carbon-deep/13 transition-colors hover:bg-tint"
                >
                  <span className="font-mono text-[13px] tabular-nums text-carbon-soft">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="truncate font-kai text-[18px] leading-tight text-carbon-deep">
                      {videoShortName(video.name)}
                    </span>
                    {subtitle ? (
                      <span className="truncate font-kai text-[13px] text-ink-muted">
                        {subtitle}
                      </span>
                    ) : null}
                  </span>
                  {video.duration ? (
                    <span className="font-mono text-[13px] tabular-nums text-carbon-soft">
                      {formatMmSs(video.duration)}
                    </span>
                  ) : null}
                  {rendition ? <Badge className="font-mono!">{rendition}</Badge> : null}
                </Link>
              );
            })
          )}
        </div>

        <aside className="flex w-[360px] shrink-0 flex-col gap-3">
          <span className="font-kai text-[13px] text-carbon-soft">此刻</span>
          <span className="font-mono text-[28px] leading-tight tabular-nums text-carbon-deep">
            {summary ? summary.total_faces_recognized.toLocaleString('en-US') : '—'}
          </span>
          <span className="font-kai text-[12px] text-ink-muted">全部影片合計的辨識次數</span>
          <div className="flex flex-col border-t border-carbon-deep/13 py-2">
            {tally.map(([label, value]) => (
              <div key={label} className="flex h-9 flex-row items-center justify-between">
                <span className="font-kai text-[13px] text-carbon-soft">{label}</span>
                <span className="font-mono text-[13px] tabular-nums text-carbon-deep">{value}</span>
              </div>
            ))}
          </div>
          <Link
            to="/player"
            className="flex h-10 items-center justify-center rounded-md border border-stamp bg-stamp font-kai text-[15px] font-bold text-paper-light transition-colors hover:bg-stamp/90"
          >
            進入播放
          </Link>
        </aside>
      </div>

      {regulars.length > 0 && (
        <section className="flex flex-col gap-4">
          <div className="flex flex-row items-end justify-between">
            <h2 className="font-kai text-[18px] font-normal text-carbon-deep">常駐面孔</h2>
            <span className="font-kai text-[12px] text-ink-muted">全部影片合計出場最多</span>
          </div>
          <div className="flex flex-row gap-6">
            {regulars.map((c) => (
              <div key={c.id} className="flex min-w-0 flex-1 flex-row items-center gap-4">
                <div className="relative h-[204px] w-[152px] shrink-0 overflow-hidden rounded bg-tint">
                  {/* The stamp sits underneath; a loaded portrait covers it, a missing one shows it. */}
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Stamp>缺相</Stamp>
                  </div>
                  {c.portrait_url ? (
                    <img
                      src={c.portrait_url}
                      alt={`${c.nickname || c.name} ${c.name}`}
                      decoding="async"
                      className="relative h-full w-full object-cover object-[50%_22%]"
                      onError={(e) => {
                        e.currentTarget.style.visibility = 'hidden';
                      }}
                    />
                  ) : null}
                </div>
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                  <span className="truncate font-kai text-[18px] leading-tight text-carbon-deep">
                    {c.nickname || c.name}
                  </span>
                  <span className="truncate font-kai text-[13px] tabular-nums text-carbon-soft">
                    {c.name} #{c.id}
                  </span>
                  <span className="font-kai text-[12px] tabular-nums text-ink-muted">
                    {c.detection_count} 次 · {c.videos_seen_in} 卷
                  </span>
                  <div className="flex flex-row items-center gap-2 pt-2">
                    <span className="font-mono text-[13px] tabular-nums text-carbon-deep">
                      {c.avg_match_score.toFixed(2)}
                    </span>
                    <Stamp band={bandFor(c.avg_match_score)} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
