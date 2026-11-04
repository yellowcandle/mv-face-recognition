import { useId, useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { Masthead, Stamp, useContestants, useCoverage } from '@mv/shared';
import { portraitSrc } from '@mv/shared/lib/portrait';
import { QUALITY_WORD } from '@mv/shared/lib/pipeline';
import type { Contestant } from '@mv/shared';

/**
 * 名冊 — the cast as a contact sheet. Every contestant is one frame with their number,
 * their name, and a stamped note when the reference set is thin. No cards: the frames
 * butt against hairline rules, the way a proof sheet does.
 */
export function Cast() {
  const { data: contestants = [], isLoading, error } = useContestants();
  const [query, setQuery] = useState('');
  const searchId = useId();
  const { data: coverage } = useCoverage();

  const all = contestants as Contestant[];

  // The contestant list only ever says good or missing; coverage is what knows a set is weak.
  const qualityById = useMemo(
    () => new Map(coverage?.contestants.map((c) => [c.id, c.quality])),
    [coverage],
  );

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
    <div className="flex min-h-full flex-1 flex-col gap-4 px-14 pb-5 pt-8">
      <Masthead title="名冊" hint="參賽者、參考照與出場次數">
        <span className="tabular-nums text-carbon-soft">
          {all.length} 位 · {withPhoto} 有相
        </span>
        <Stamp tone="muted">唯讀</Stamp>
      </Masthead>

      <div className="flex flex-row items-center gap-3">
        <div className="relative w-[420px]">
          <Search
            size={16}
            aria-hidden="true"
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-carbon-soft"
          />
          <input
            id={searchId}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={all.length ? `搜尋 ${all.length} 位參賽者…` : '搜尋參賽者…'}
            className="h-10 w-full rounded-md border border-carbon-deep/33 bg-transparent pl-9 pr-3 font-kai text-[14px] text-carbon-deep placeholder:text-ink-muted"
          />
        </div>
        <label htmlFor={searchId} className="font-kai text-[12px] text-ink-muted">
          編號、姓名或暱稱
        </label>
        <span className="ml-auto font-mono text-[13px] tabular-nums text-carbon-soft">
          {filtered.length} / {all.length}
        </span>
      </div>

      {isLoading ? (
        <div className="py-16 text-center font-kai text-[13px] text-ink-muted">正在調閱名冊…</div>
      ) : error ? (
        <div className="rounded-md border border-stamp/40 px-4 py-10 text-center font-kai text-[13px] text-stamp">
          讀不到名冊 — API 未回應。
        </div>
      ) : filtered.length === 0 ? (
        <div className="border-y border-carbon-deep/13 px-4 py-14 text-center">
          <div className="font-kai text-[15px] text-carbon-deep">名冊裡沒有這個人</div>
          <div className="mt-1 font-kai text-[13px] text-ink-muted">換個編號或名字試試。</div>
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(80px,1fr))] border-l border-t border-carbon-deep/33">
          {filtered.map((c) => {
            // Only the cropped derivative is public; no portrait_url means the 缺相 stamp shows.
            const src = c.portrait_url ?? null;
            const quality = qualityById.get(c.id) ?? c.quality;
            return (
              <figure
                key={c.id}
                className="flex min-w-0 flex-col border-b border-r border-carbon-deep/33"
              >
                <div className="relative aspect-[83/76] overflow-hidden bg-tint">
                  {/* The stamp sits underneath; a loaded portrait covers it, a missing one shows it. */}
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Stamp>缺相</Stamp>
                  </div>

                  {src ? (
                    <img
                      src={portraitSrc(src, 128)!}
                      alt={`${c.nickname} ${c.name}`}
                      loading="lazy"
                      decoding="async"
                      className="relative h-full w-full object-cover object-[50%_22%]"
                      onError={(e) => {
                        // A failed resize falls back to the original before the 缺相 stamp shows.
                        if (e.currentTarget.src.includes('/cdn-cgi/image/'))
                          e.currentTarget.src = src;
                        else e.currentTarget.style.visibility = 'hidden';
                      }}
                    />
                  ) : null}

                  {quality !== 'good' && c.reference_count > 0 && (
                    <Stamp
                      tone={quality === 'missing' ? 'stamp' : 'muted'}
                      className="absolute right-1 top-1 bg-ground/93"
                    >
                      {QUALITY_WORD[quality]}
                    </Stamp>
                  )}
                </div>

                <figcaption className="flex flex-col gap-0.5 p-1">
                  <span className="truncate font-kai text-[13px] leading-tight text-carbon-deep">
                    {c.nickname}
                  </span>
                  <span className="flex flex-row items-center gap-1">
                    <span className="font-mono text-[12px] tabular-nums text-carbon-soft">
                      {String(c.id).padStart(2, '0')}
                    </span>
                    <span className="truncate font-kai text-[12px] text-ink-muted">{c.name}</span>
                  </span>
                </figcaption>
              </figure>
            );
          })}
        </div>
      )}

      <div className="mt-auto flex flex-row items-center justify-between font-kai text-[12px] text-ink-muted">
        <span>相片來源：精選歷史相片集 · 臉部裁切為衍生縮圖</span>
        <span>唯讀檢視 · 所有改動在後台</span>
      </div>
    </div>
  );
}
