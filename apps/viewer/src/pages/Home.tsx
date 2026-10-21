import { Link } from 'react-router';
import { Masthead, useVideos } from '@mv/shared';

/**
 * 圖庫 — the library is the stack of reels already filed, one row per slip:
 * REEL number, the programme it came from, and the stamp that opens it.
 */
export function Home() {
  const { data: videos = [], isLoading } = useVideos();

  return (
    <div className="flex min-h-0 flex-1 flex-col px-10 pb-10 pt-7">
      <Masthead eyebrow="MV FACE RECOGNITION · 全民造星 IV" title="圖庫" latin="FILED REELS">
        <div className="flex flex-col items-end gap-0.5">
          <span className="font-mono text-[9px] tracking-[0.2em] text-ledger">ON FILE</span>
          <span className="font-mono text-[12px] text-carbon">{videos.length} 卷</span>
        </div>
        <div className="-rotate-[7deg] rounded-[4px] border-2 border-stamp px-3 py-1.5">
          <div className="font-serif text-[15px] font-bold tracking-[0.14em] text-stamp">唯讀</div>
          <div className="font-mono text-[7px] tracking-[0.18em] text-stamp">PUBLIC · COPY 2</div>
        </div>
      </Masthead>

      <div className="mt-4 h-px bg-carbon/45" />

      <div className="flex flex-row items-baseline justify-between pt-3 pb-4">
        <span className="font-kai text-[15px] font-bold text-carbon">已存影片</span>
        <span className="font-mono text-[9px] tracking-[0.18em] text-ledger">按處理次序編排</span>
      </div>

      <div className="flex flex-row items-center gap-6 border-b border-carbon/40 pb-2.5">
        <span className="w-[54px] font-mono text-[8px] tracking-[0.18em] text-ledger">REEL</span>
        <span className="w-[420px] font-mono text-[8px] tracking-[0.18em] text-ledger">
          PROGRAMME
        </span>
        <span className="flex-1" />
        <span className="font-mono text-[8px] tracking-[0.18em] text-ledger">OPEN</span>
      </div>

      {isLoading ? (
        <div className="py-16 text-center font-kai text-[13px] text-carbon-soft">正在調閱…</div>
      ) : videos.length === 0 ? (
        <div className="mt-2 border border-dashed border-carbon/35 px-4 py-14 text-center">
          <div className="font-kai text-[15px] font-bold text-carbon-deep">
            尚未有任何已處理影片
          </div>
          <div className="mt-1 font-kai text-[12px] text-carbon-soft">
            處理完成的影片會存進這裡，附帶每一格的人臉紀錄。
          </div>
        </div>
      ) : (
        <div className="flex flex-col">
          {videos.map((video, i) => (
            <Link
              key={video.id}
              to={`/player?video=${encodeURIComponent(video.id)}`}
              className="group flex flex-row items-center gap-6 border-b border-carbon/20 py-4 transition-colors hover:bg-paper-light"
            >
              <span className="w-[54px] font-mono text-[19px] text-carbon">
                {String(i + 1).padStart(2, '0')}
              </span>
              <span className="flex w-[420px] flex-col gap-1">
                <span className="font-kai text-[17px] font-bold leading-snug text-carbon-deep">
                  {video.name}
                </span>
                <span className="font-mono text-[9px] tracking-[0.14em] text-ledger">
                  ID {video.id}
                </span>
              </span>
              <span className="flex-1" />
              <span className="border border-carbon/50 px-3 py-1.5 font-kai text-[11px] tracking-[0.14em] text-carbon transition-colors group-hover:border-stamp group-hover:text-stamp">
                開啟
              </span>
            </Link>
          ))}
        </div>
      )}

      <div className="flex-1" />
      <div className="flex flex-row items-center justify-between border-t border-carbon/25 pt-3">
        <span className="font-mono text-[9px] tracking-[0.18em] text-ledger">
          96 位參賽者 · 逐格人臉紀錄
        </span>
        <span className="font-kai text-[11px] text-carbon-soft">唯讀檢視 · 所有改動在後台</span>
      </div>
    </div>
  );
}
