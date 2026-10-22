import { Link } from 'react-router';
import { BAND_STAMP, Masthead, bandFor, useCoverage, useVideos } from '@mv/shared';

/**
 * 點唱單 — the request slip. Five reels filed on the left, the current tally on the
 * right, and the faces that keep returning along the foot of the page.
 */
export function Home() {
  const { data: videos = [], isLoading } = useVideos();
  const { data: coverage } = useCoverage();

  const summary = coverage?.summary;
  const contestants = coverage?.contestants ?? [];

  // "Most seen" is a count, not a recency: the read model has no cross-reel timeline.
  const mostSeen = [...contestants]
    .sort((a, b) => b.detection_count - a.detection_count)
    .slice(0, 4);

  return (
    <div className="flex min-h-0 flex-1 flex-col px-14 pb-10 pt-12">
      <Masthead eyebrow="MV FACE RECOGNITION · 全民造星 IV" title="點唱單" latin="JUKEBOX" />

      <div className="mt-6 h-px bg-carbon/45" />

      <div className="flex flex-row gap-14 pt-7">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex flex-row items-baseline justify-between pb-4">
            <span className="font-mono text-[10px] tracking-[0.28em] text-ledger">
              REEL 01 — {String(videos.length).padStart(2, '0')}
            </span>
            <span className="font-mono text-[10px] tracking-[0.14em] text-ledger">
              {summary ? `${summary.total} 位 · ${summary.total_faces_recognized.toLocaleString('en-US')} 辨識` : '—'}
            </span>
          </div>

          {isLoading ? (
            <div className="py-16 text-center font-kai text-[13px] text-carbon-soft">正在調閱…</div>
          ) : videos.length === 0 ? (
            <div className="border border-dashed border-carbon/35 px-4 py-14 text-center">
              <div className="font-kai text-[15px] font-bold text-carbon-deep">尚未有已處理影片</div>
              <div className="mt-1 font-kai text-[12px] text-carbon-soft">
                處理完成的影片會存進這裡。
              </div>
            </div>
          ) : (
            videos.map((video, index) => (
              <Link
                key={video.id}
                to={`/player?video=${encodeURIComponent(video.id)}`}
                className="group flex flex-row items-center justify-between gap-6 border-b border-carbon/20 py-5 transition-colors hover:bg-paper-light"
              >
                <div className="flex min-w-0 flex-row items-center gap-5">
                  <span className="w-6 shrink-0 font-mono text-[11px] text-carbon-soft">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className="truncate font-serif text-[22px] font-bold leading-tight text-carbon-deep">
                    {video.name.replace(/^\d+-/, '').replace(/^《全民造星IV》/, '').trim() ||
                      video.name}
                  </span>
                </div>
                <div className="flex shrink-0 flex-row items-center gap-4">
                  <span className="border border-stamp/50 px-2 py-1 font-mono text-[8px] tracking-[0.16em] text-stamp transition-colors group-hover:border-stamp group-hover:bg-stamp group-hover:text-paper-light">
                    1080P
                  </span>
                </div>
              </Link>
            ))
          )}
        </div>

        <aside className="flex w-[360px] shrink-0 flex-col gap-4">
          <div className="flex flex-col gap-3 border border-carbon/25 bg-paper-light p-6">
            <span className="font-mono text-[9px] tracking-[0.26em] text-ledger">此刻 / NOW</span>
            <span className="font-serif text-[52px] font-bold leading-none text-carbon-deep">
              {summary ? summary.total_faces_recognized.toLocaleString('en-US') : '—'}
            </span>
            <span className="font-kai text-[12px] text-carbon-soft">五卷合計的辨識次數</span>
            <div className="h-px bg-carbon/20" />
            {[
              ['平均配對分數', summary ? summary.avg_match_score.toFixed(2) : '—'],
              ['出場參賽者', summary ? `${summary.total} 位` : '—'],
              ['辨識率', summary ? `${(summary.recognition_rate * 100).toFixed(1)}%` : '—'],
            ].map(([label, value]) => (
              <div key={label} className="flex flex-row items-baseline justify-between py-1">
                <span className="font-kai text-[12px] text-carbon-soft">{label}</span>
                <span className="font-mono text-[11px] text-carbon-deep">{value}</span>
              </div>
            ))}
          </div>

          <Link
            to="/player"
            className="flex flex-row items-center justify-center gap-2.5 border border-stamp bg-stamp px-4 py-4 transition-colors hover:bg-carbon"
          >
            <span className="font-kai text-[14px] tracking-[0.12em] text-paper-light">進入播放</span>
            <span className="font-mono text-[10px] tracking-[0.24em] text-paper-light/70">PLAY</span>
          </Link>
        </aside>
      </div>

      {mostSeen.length > 0 && (
        <div className="flex flex-col gap-4 pt-10">
          <div className="flex flex-row items-baseline justify-between">
            <span className="font-serif text-[16px] font-bold text-carbon-deep">常駐面孔</span>
            <span className="font-mono text-[9px] tracking-[0.24em] text-ledger">
              MOST SEEN · ACROSS FIVE REELS
            </span>
          </div>
          <div className="flex flex-row gap-4">
            {mostSeen.map((c) => {
              const band = bandFor(c.avg_match_score);
              return (
                <div
                  key={c.id}
                  className="flex min-w-0 flex-1 flex-col gap-2.5 border border-carbon/25 bg-paper-light px-5 py-4"
                >
                  <span className="truncate font-serif text-[18px] font-bold leading-tight text-carbon-deep">
                    {c.nickname || c.name}
                  </span>
                  <span className="font-kai text-[11px] text-carbon-soft">{c.name}</span>
                  <span className="font-mono text-[9px] tracking-[0.14em] text-ledger">
                    {c.detection_count} 次 · {c.videos_seen_in} 卷
                  </span>
                  <div className="flex flex-row items-center justify-between pt-1.5">
                    <span className="font-mono text-[10px] text-carbon-soft">
                      {c.avg_match_score.toFixed(2)}
                    </span>
                    <span
                      className={`inline-block -rotate-2 border px-1.5 py-0.5 font-kai text-[10px] tracking-[0.12em] ${BAND_STAMP[band].ink}`}
                    >
                      {BAND_STAMP[band].word}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
