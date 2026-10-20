import { Link } from 'react-router';
import { useVideos, useFlaggedFaces } from '@mv/shared';

/** 儀表 — the operator's desk: what is filed, what is waiting, where to go. */
export function Dashboard() {
  const { data: videos = [] } = useVideos();
  const { data: flagged = [] } = useFlaggedFaces();

  const pending = flagged.filter((f) => f.status === 'pending').length;
  const accepted = flagged.filter((f) => f.status === 'accepted').length;

  const counters = [
    { cn: '已存影片', latin: 'REELS', value: videos.length, ink: 'text-carbon' },
    { cn: '參賽者', latin: 'CAST', value: 96, ink: 'text-carbon' },
    { cn: '待核', latin: 'PENDING', value: pending, ink: 'text-carbon' },
    { cn: '已核對', latin: 'ACCEPTED', value: accepted, ink: 'text-carbon' },
  ];

  return (
    <div className="flex min-h-0 flex-1 flex-col px-9 pb-8 pt-7">
      <div className="flex flex-row items-end justify-between gap-6">
        <div className="flex flex-col gap-1.5">
          <div className="font-mono text-[10px] tracking-[0.28em] text-carbon-soft">
            BACK OFFICE · LOCAL ONLY · 127.0.0.1
          </div>
          <div className="flex flex-row items-baseline gap-3.5">
            <h1 className="font-serif text-[44px] font-black leading-none tracking-[0.06em] text-carbon">
              儀表
            </h1>
            <span className="font-mono text-[11px] tracking-[0.26em] text-ledger">DESK</span>
          </div>
        </div>
        <div className="pb-1 font-kai text-[12px] text-carbon-soft">
          所有寫入只在這一台機器上發生
        </div>
      </div>

      <div className="mt-4 h-px bg-carbon/45" />

      <div className="flex flex-row items-end gap-12 py-4">
        {counters.map((c) => (
          <div key={c.latin} className="flex flex-col gap-1">
            <span className="font-mono text-[8px] tracking-[0.2em] text-ledger">
              {c.cn} {c.latin}
            </span>
            <span className={`font-mono text-[26px] leading-none ${c.ink}`}>{c.value}</span>
          </div>
        ))}
      </div>

      <div className="h-px bg-carbon/20" />

      <div className="flex flex-row gap-10 pt-5">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex flex-row items-baseline justify-between pb-2">
            <span className="font-kai text-[15px] font-bold text-carbon">待核紀錄</span>
            <Link to="/flagging" className="font-mono text-[9px] tracking-[0.14em] text-stamp">
              前往托盤 →
            </Link>
          </div>
          {flagged.length === 0 ? (
            <div className="border border-dashed border-carbon/35 px-4 py-10 text-center font-kai text-[12px] text-carbon-soft">
              目前沒有待核的人臉標記。
            </div>
          ) : (
            <div className="flex flex-col">
              {flagged.slice(0, 6).map((f) => (
                <div
                  key={f.id}
                  className="flex flex-row items-center gap-3 border-b border-carbon/15 py-2.5"
                >
                  <span className="w-[46px] font-mono text-[11px] text-carbon-soft">
                    {String(Math.floor(f.timestamp / 60)).padStart(2, '0')}:
                    {String(Math.floor(f.timestamp % 60)).padStart(2, '0')}
                  </span>
                  <span className="flex-1 truncate font-kai text-[14px] font-bold text-carbon-deep">
                    #{f.contestant_id}
                  </span>
                  <span className="font-mono text-[9px] tracking-[0.12em] text-ledger">
                    {f.video_id}
                  </span>
                  <span
                    className={`-rotate-2 border px-1.5 py-0.5 font-kai text-[10px] ${
                      f.status === 'pending'
                        ? 'border-stamp text-stamp'
                        : f.status === 'accepted'
                          ? 'border-carbon text-carbon'
                          : 'border-ledger text-ledger'
                    }`}
                  >
                    {f.status === 'pending' ? '待核' : f.status === 'accepted' ? '已核對' : '作廢'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex w-[300px] shrink-0 flex-col">
          <div className="pb-2 font-kai text-[15px] font-bold text-carbon">快捷</div>
          <div className="flex flex-col">
            {[
              { to: '/flagging', cn: '待核托盤', latin: 'FLAGS' },
              { to: '/contestants', cn: '參賽者名冊', latin: 'CAST' },
              { to: '/player', cn: '播放與校正', latin: 'PLAYER' },
              { to: '/embedding-workbench', cn: '向量工作台', latin: 'EMBED' },
              { to: '/processing', cn: '處理進度', latin: 'PROCESS' },
            ].map((l) => (
              <Link
                key={l.to}
                to={l.to}
                className="group flex flex-row items-center justify-between border-b border-carbon/20 py-2.5"
              >
                <span className="font-kai text-[14px] font-bold text-carbon-deep group-hover:text-stamp">
                  {l.cn}
                </span>
                <span className="font-mono text-[8px] tracking-[0.16em] text-ledger">{l.latin}</span>
              </Link>
            ))}
          </div>
        </div>
      </div>

      <div className="flex-1" />
      <div className="flex flex-row items-center justify-between border-t border-carbon/25 pt-3">
        <span className="font-mono text-[9px] tracking-[0.18em] text-ledger">
          分級為暫定值，依實測誤配率調整
        </span>
        <span className="font-kai text-[11px] text-carbon-soft">存根 · 可寫</span>
      </div>
    </div>
  );
}
