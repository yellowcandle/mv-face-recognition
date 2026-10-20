import { useMemo, useState } from 'react';
import { useContestants } from '@mv/shared';
import type { Contestant } from '@mv/shared';

const QUALITY_WORD: Record<Contestant['quality'], string> = {
  good: '齊全',
  weak: '偏弱',
  missing: '缺',
};

/**
 * 名冊 — the cast as a contact sheet. Every contestant is one frame with their number,
 * their name in hand, and a stamped note when the reference set is thin. No cards:
 * the frames butt against hairline rules, the way a proof sheet does.
 */
export function Cast() {
  const { data: contestants = [], isLoading, error } = useContestants();
  const [query, setQuery] = useState('');

  const all = contestants as Contestant[];

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return all;
    return all.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.nickname.toLowerCase().includes(q) ||
        String(c.id).includes(q),
    );
  }, [all, query]);

  // Count portraits, not reference sets: the historical set can supply a thumbnail for a
  // contestant with no Instagram photos on disk.
  const withPhoto = all.filter((c) => c.portrait_url || c.reference_count > 0).length;

  return (
    <div className="flex min-h-0 flex-1 flex-col px-10 pb-8 pt-7">
      <div className="flex flex-row items-end justify-between gap-6">
        <div className="flex flex-col gap-1.5">
          <div className="font-mono text-[10px] tracking-[0.28em] text-carbon-soft">
            MV FACE RECOGNITION · 全民造星 IV
          </div>
          <div className="flex flex-row items-baseline gap-3.5">
            <h1 className="font-serif text-[46px] font-black leading-none tracking-[0.06em] text-carbon">
              名冊
            </h1>
            <span className="font-mono text-[11px] tracking-[0.26em] text-ledger">CAST SHEET</span>
          </div>
        </div>

        <div className="flex flex-row items-end gap-8 pb-1">
          <div className="flex flex-col items-end gap-0.5">
            <span className="font-mono text-[9px] tracking-[0.2em] text-ledger">ON FILE</span>
            <span className="font-mono text-[12px] text-carbon">
              {all.length} 位 · {withPhoto} 有相
            </span>
          </div>
          <div className="-rotate-[7deg] rounded-[4px] border-2 border-stamp px-3 py-1.5">
            <div className="font-serif text-[15px] font-bold tracking-[0.14em] text-stamp">唯讀</div>
            <div className="font-mono text-[7px] tracking-[0.18em] text-stamp">PUBLIC · COPY 2</div>
          </div>
        </div>
      </div>

      <div className="mt-4 h-px bg-carbon/45" />

      <div className="flex flex-row items-end justify-between gap-6 py-3">
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="font-mono text-[8px] tracking-[0.2em] text-ledger">
            SEARCH 編號 / 姓名 / 暱稱
          </span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜尋 96 位參賽者…"
            className="w-full max-w-[420px] border-b border-carbon/45 bg-transparent pb-1.5 font-kai text-[15px] text-carbon-deep placeholder:text-ledger focus:border-stamp focus:outline-none"
          />
        </div>
        <span className="font-mono text-[10px] text-carbon-soft">
          {filtered.length} / {all.length}
        </span>
      </div>

      {isLoading ? (
        <div className="py-16 text-center font-kai text-[13px] text-carbon-soft">正在調閱名冊…</div>
      ) : error ? (
        <div className="mt-1 border border-stamp/40 bg-stamp/5 px-4 py-10 text-center font-kai text-[13px] text-stamp">
          讀不到名冊 — API 未回應。
        </div>
      ) : filtered.length === 0 ? (
        <div className="mt-1 border border-dashed border-carbon/35 px-4 py-14 text-center">
          <div className="font-kai text-[15px] font-bold text-carbon-deep">名冊裡沒有這個人</div>
          <div className="mt-1 font-kai text-[12px] text-carbon-soft">換個編號或名字試試。</div>
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(148px,1fr))] border-l border-t border-carbon/25">
          {filtered.map((c) => {
            // Only the cropped derivative is public; no portrait_url means the 缺相 stamp shows.
            const src = c.portrait_url ?? null;
            return (
              <figure key={c.id} className="group flex flex-col border-b border-r border-carbon/25 bg-paper">
                <div className="relative aspect-[3/4] overflow-hidden bg-paper-dark">
                  {/* The stamp sits underneath; a loaded portrait covers it, a missing one shows it. */}
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="-rotate-6 border border-ledger px-2 py-1 font-kai text-[11px] tracking-[0.18em] text-ledger">
                      缺相
                    </span>
                  </div>

                  {src ? (
                    <img
                      src={src}
                      alt={`${c.nickname} ${c.name}`}
                      loading="lazy"
                      decoding="async"
                      className="relative h-full w-full object-cover object-[50%_22%] transition-transform duration-300 group-hover:scale-[1.03]"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.visibility = 'hidden';
                      }}
                    />
                  ) : null}

                  {c.quality !== 'good' && c.reference_count > 0 && (
                    <span className="absolute right-1.5 top-1.5 -rotate-2 border border-stamp bg-paper-light/85 px-1 py-0.5 font-kai text-[9px] tracking-[0.1em] text-stamp">
                      {QUALITY_WORD[c.quality]}
                    </span>
                  )}
                </div>

                <figcaption className="flex flex-col gap-0.5 border-t border-carbon/15 px-2 py-1.5">
                  <div className="flex flex-row items-baseline gap-1.5">
                    <span className="font-mono text-[10px] text-carbon-soft">
                      {String(c.id).padStart(2, '0')}
                    </span>
                    <span className="truncate font-kai text-[14px] font-bold leading-tight text-carbon-deep group-hover:text-stamp">
                      {c.nickname}
                    </span>
                  </div>
                  <span className="truncate font-kai text-[11px] text-carbon-soft">{c.name}</span>
                </figcaption>
              </figure>
            );
          })}
        </div>
      )}

      <div className="flex-1" />
      <div className="mt-4 flex flex-row items-center justify-between border-t border-carbon/25 pt-3">
        <span className="font-mono text-[9px] tracking-[0.18em] text-ledger">
          相片來源 精選歷史相片集 CURATED HISTORICAL SET · 臉部裁切為衍生縮圖
        </span>
        <span className="font-kai text-[11px] text-carbon-soft">唯讀檢視 · 所有改動在後台</span>
      </div>
    </div>
  );
}
