import { useEffect } from 'react';
import { useNavigate } from 'react-router';
import { Button, Card, Masthead, Stamp, bandFor } from '@mv/shared';
import {
  CONTESTANT_COUNT,
  CUTOFF_SWEEP,
  FACE_SIZE_CEILING,
  HIRES_COMPARISON,
  JOB_THRESHOLD,
  MATCHER_CHECK,
  NAMED_PRESENT,
  OPEN_TOP1,
  POST_PHOTOS,
  POST_REPLIES,
  UNSEEN_REPLY_AUTHORS,
  REFERENCE_COUNT,
  ROSTER_NOISE,
  SITE_THRESHOLD,
  STREET_IMAGES,
  TOTALS,
  VIVA_COVERAGE,
  type StreetImage,
} from './streetPhotos.data';

/**
 * 街拍 — two frames shot outside the reels, run through the same detector and matcher, with the
 * acceptance threshold dropped for this job.
 *
 * What the page is for: the pipeline is calibrated on 1080p reels where a face is a few hundred
 * pixels across. These frames are group street shots, so the faces are 10–40 px and at the site
 * threshold (0.412) nothing passes. At the job threshold (0.35) exactly one face does, and it is
 * shown with the price of the lower bar in the same breath: at 0.35 more than one reference photo
 * in ten matches a stranger, so the candidate is a candidate, never an identification.
 */

const STREET_TITLE = '銅鑼灣呢隊係咩團？全民造星 IV · 街拍判讀';
const CELL = 'border-b border-carbon-deep/13 px-2 py-1.5 text-left align-baseline';
const NUM = 'font-mono text-[13px] tabular-nums';

function Figure({ image }: { image: StreetImage }) {
  const best = image.faces.reduce((a, f) => (f.top1 > a.top1 ? f : a), image.faces[0]);
  return (
    <figure className="flex min-w-0 flex-col gap-2">
      <div className="relative overflow-hidden rounded-md border border-carbon-deep/13 bg-tint">
        {/* Boxes are frame fractions, so they scale with the rendered image and nothing else. */}
        <img
          src={image.src}
          alt={image.alt}
          width={image.width}
          height={image.height}
          loading="lazy"
          className="block w-full"
        />
        {image.faces.map((face) => {
          const [x1, y1, x2, y2] = face.box;
          return (
            <span
              key={face.i}
              aria-hidden="true"
              className={`pointer-events-none absolute border ${
                face.candidate ? 'border-2 border-stamp' : 'border border-carbon-deep/80'
              }`}
              style={{
                left: `${x1 * 100}%`,
                top: `${y1 * 100}%`,
                width: `${(x2 - x1) * 100}%`,
                height: `${(y2 - y1) * 100}%`,
              }}
            >
              <span className="absolute -top-[15px] left-0 font-mono text-[11px] leading-none text-carbon-deep">
                {face.i}
              </span>
            </span>
          );
        })}
      </div>
      <figcaption className="flex flex-col gap-1 font-kai text-[13px] leading-relaxed text-carbon-soft">
        <span>{image.caption}</span>
        <span className="font-mono text-[12px] tabular-nums text-ink-muted">
          {image.faces.length} 框 · 最高 {best.top1.toFixed(3)} · 距本站門檻{' '}
          {(SITE_THRESHOLD - best.top1).toFixed(3)}
        </span>
      </figcaption>
    </figure>
  );
}

export function StreetPhotos() {
  const navigate = useNavigate();

  // The shell's title is the 點唱單 page's; a tab opened from a shared link should say what this is.
  // On the way out, fall back to the shell's own title — that is what a fresh load of any other
  // route shows, so leaving the street report must not leave its title behind.
  useEffect(() => {
    document.title = STREET_TITLE;
    return () => {
      document.title = '點唱單 · MV Face Recognition';
    };
  }, []);

  const bestCandidate = STREET_IMAGES.flatMap((im) =>
    im.faces.map((face) => ({ face, image: im })),
  ).find((r) => r.face.candidate);
  const jobRate = CUTOFF_SWEEP.find((r) => r.cutoff === JOB_THRESHOLD)?.rate ?? 0;

  return (
    // The root stays a plain block: as a `flex-1` column it hands its children a definite height,
    // and they shrink into it — the tables would collapse to their borders.
    <div className="min-h-full flex-1">
      <div className="flex flex-col gap-6 px-4 pb-10 pt-6 sm:px-14 sm:pt-8">
        <Masthead title="街拍" hint="場外兩張 · 人手認得九位 · 機器認得一位">
          <span className="font-mono text-[12px] tabular-nums">2026-11-15</span>
        </Masthead>

        {/* Arrival block: most readers come from a link on the original Threads post, asking what
            this group is. Answer that first, then route them into the site proper. */}
        <div className="flex flex-col gap-3 rounded-md border border-stamp/40 bg-stamp/5 p-4 sm:p-5">
          <span className="font-kai text-[13px] font-bold tracking-wide text-stamp">答案</span>
          <p className="font-kai text-[22px] leading-snug text-carbon-deep sm:text-[26px]">
            銅鑼灣那一隊「疑似女團」，是《全民造星 IV》的參賽者——2021 年那一屆，96 位。
          </p>
          <p className="max-w-[68ch] font-kai text-[14px] leading-relaxed text-carbon">
            帖文下面兩種答法都對：其中 Carina（李晞彤）與 Ada（姜咏鑫）已於 2024 年以英皇女團 VIVA
            出道，所以「造星 IV」與「VIVA 拍 MV」說的是同一批人。
          </p>
          <p className="max-w-[68ch] font-kai text-[14px] leading-relaxed text-carbon">
            這個站用同一套臉部辨識，把《前傳》三部曲等 MV 逐格認人：每個框對過 638
            個參考向量，分數是原始餘弦，逐條可以覆核。下面是我拿這幾張街拍去跑的結果，最後一節講為什麼人眼一望就認得、機器卻幾乎認不出。
          </p>
          <div className="flex flex-row flex-wrap gap-2">
            <Button variant="primary" size="lg" onClick={() => navigate('/')}>
              入去點唱單
            </Button>
            <Button size="lg" onClick={() => navigate('/cast')}>
              睇名冊
            </Button>
            <Button size="lg" onClick={() => navigate('/analytics')}>
              睇辨識紀錄
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-y-4 border-y border-carbon-deep/13 py-4 sm:grid-cols-4">
          {[
            { label: '偵測人臉', value: TOTALS.faces.toLocaleString() },
            { label: '過檻', value: TOTALS.accepted.toLocaleString() },
            { label: '最高餘弦', value: TOTALS.best.toFixed(3) },
            { label: '本頁門檻', value: JOB_THRESHOLD.toFixed(3) },
          ].map((s) => (
            <div key={s.label} className="flex flex-col gap-1">
              <span className="font-kai text-[13px] text-carbon-soft">{s.label}</span>
              <span className="font-mono text-[28px] leading-tight tabular-nums text-carbon-deep">
                {s.value}
              </span>
            </div>
          ))}
        </div>

        <p className="max-w-[68ch] font-kai text-[14px] leading-relaxed text-carbon">
          相片出自 Threads 一篇公開帖文：有人見到「呢隊疑似女團」在銅鑼灣拍 MV，問這是什麼團（
          <a
            href="https://www.threads.com/@zisha_1001/post/DfuWFhMH-4X"
            target="_blank"
            rel="noreferrer noopener"
            className="text-carbon-deep underline decoration-carbon-deep/30 underline-offset-2 hover:decoration-carbon-deep"
          >
            @zisha_1001
          </a>
          ）。答案看過節目的人都認得——都是《全民造星
          IV》的人。人手一眼認得九位；同一個場景交給管線，只認得一位，而且要在下調門檻之下。
        </p>

        <p className="max-w-[68ch] font-kai text-[14px] leading-relaxed text-carbon">
          這一頁按同一批數字重跑，只改一個旋鈕：接受門檻由本站預設{' '}
          <span className="font-mono tabular-nums">{SITE_THRESHOLD.toFixed(3)}</span>（實測 1%
          假配對邊界）下調至{' '}
          <span className="font-mono tabular-nums">{JOB_THRESHOLD.toFixed(3)}</span>
          。下調的代價是量得到的：在這個門檻上，
          <span className="font-mono tabular-nums">{(jobRate * 100).toFixed(1)}%</span>{' '}
          的參考向量會錯配陌生人。二十三個框之中，只有一個過檻。
        </p>

        {bestCandidate?.face.candidate && (
          <Card padding="md" className="flex max-w-[68ch] flex-col gap-2 border-stamp/40">
            <div className="flex flex-row flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="font-kai text-[13px] text-carbon-soft">
                {bestCandidate.image.key === 'a' ? '一 · 過路' : '二 · 排隊'} 第{' '}
                {bestCandidate.face.i} 個框
              </span>
              <span className="font-kai text-[20px] leading-tight text-carbon-deep">
                {bestCandidate.face.candidate.name}
              </span>
              <span className="font-kai text-[14px] text-carbon">
                （{bestCandidate.face.candidate.nickname} · 編號 {bestCandidate.face.candidate.id}）
              </span>
              <Stamp band={bandFor(bestCandidate.face.top1)} />
            </div>
            <span className="font-mono text-[12px] tabular-nums text-ink-muted">
              cosine {bestCandidate.face.top1.toFixed(3)} · 次高{' '}
              {bestCandidate.face.top2.toFixed(3)} · 相差 {bestCandidate.face.margin.toFixed(3)} ·
              框 {bestCandidate.face.px[0]}×{bestCandidate.face.px[1]} px
            </span>
            <span className="max-w-[62ch] font-kai text-[13px] leading-relaxed text-carbon-soft">
              唯一過檻的框，差距 0.219 也是全批最闊的一格。它是候選，不是認定：36×44
              像素的臉已經被降採樣吃掉一部分餘弦，而 0.35 這個門檻本身有大約一成的錯配率。
            </span>
          </Card>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {STREET_IMAGES.map((image) => (
            <Figure key={image.key} image={image} />
          ))}
        </div>

        <Card padding="none" className="overflow-x-auto">
          <table className="w-full min-w-[600px] border-collapse">
            <caption className="px-3 py-2 text-left font-kai text-[13px] text-carbon-soft">
              逐框判讀 · 餘弦為原始 cosine，越高越相似 · 只有過檻的框列名字
            </caption>
            <thead>
              <tr className="font-kai text-[12px] text-ink-muted">
                <th className={CELL}>圖</th>
                <th className={CELL}>#</th>
                <th className={CELL}>框（像素）</th>
                <th className={CELL}>偵測分</th>
                <th className={CELL}>最高餘弦</th>
                <th className={CELL}>次高</th>
                <th className={CELL}>相差</th>
                <th className={CELL}>判定</th>
              </tr>
            </thead>
            <tbody>
              {STREET_IMAGES.map((image) =>
                image.faces.map((face) => (
                  <tr
                    key={`${image.key}-${face.i}`}
                    className={face.candidate ? 'bg-stamp/5' : 'hover:bg-tint'}
                  >
                    <td className={`${CELL} font-kai text-[13px] text-carbon-soft`}>
                      {image.key === 'a' ? '一' : '二'}
                    </td>
                    <td className={`${CELL} ${NUM} text-carbon-deep`}>{face.i}</td>
                    <td className={`${CELL} ${NUM} text-carbon-soft`}>
                      {face.px[0]}×{face.px[1]}
                    </td>
                    <td className={`${CELL} ${NUM} text-carbon-soft`}>
                      {face.det_score.toFixed(2)}
                    </td>
                    <td className={CELL}>
                      <span className="flex flex-row items-center gap-2">
                        <span className={`${NUM} text-carbon-deep`}>{face.top1.toFixed(3)}</span>
                        <Stamp band={bandFor(face.top1)} />
                      </span>
                    </td>
                    <td className={`${CELL} ${NUM} text-ink-muted`}>{face.top2.toFixed(3)}</td>
                    <td className={`${CELL} ${NUM} text-ink-muted`}>{face.margin.toFixed(3)}</td>
                    <td className={`${CELL} font-kai text-[13px]`}>
                      {face.candidate ? (
                        <span className="text-carbon-deep">{face.candidate.nickname}</span>
                      ) : (
                        <span className="text-ink-muted">未過檻</span>
                      )}
                    </td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </Card>

        <div className="flex flex-col gap-4">
          <h2 className="font-kai text-[20px] leading-tight text-carbon-deep">帖文下的回覆</h2>

          <p className="max-w-[76ch] font-kai text-[14px] leading-relaxed text-carbon">
            63 個回覆之中，未登入只讀到五個。三種答案：造星
            IV、VIVA、Cookies。前兩種其實同指一批人——VIVA 的 {VIVA_COVERAGE.members} 位成員之中，
            {VIVA_COVERAGE.inRoster} 位（Carina 15 號、Ada 27 號）本身就是造星 IV
            的人；其餘兩位（馬思惠、張鈊貽）不在這 96
            人名冊裡，所以本站對她們連一個參考向量都沒有，永遠認不出。
          </p>

          <div className="flex max-w-[76ch] flex-col border-t border-carbon-deep/13">
            {POST_REPLIES.map((r) => (
              <div
                key={r.handle}
                className="flex flex-col gap-1 border-b border-carbon-deep/13 py-2.5"
              >
                <a
                  href={`https://www.threads.com/@${r.handle}`}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="font-mono text-[12px] text-carbon-soft underline decoration-carbon-deep/20 underline-offset-2 hover:decoration-carbon-deep"
                >
                  @{r.handle}
                </a>
                <span className="font-kai text-[14px] leading-relaxed text-carbon">{r.text}</span>
                {r.verdict ? (
                  <span className="font-kai text-[13px] leading-relaxed text-ink-muted">
                    → {r.verdict}
                  </span>
                ) : null}
              </div>
            ))}
          </div>

          <p className="max-w-[76ch] font-kai text-[14px] leading-relaxed text-carbon">
            回覆之中還有{' '}
            {UNSEEN_REPLY_AUTHORS.map((c) => `${c.name}（${c.nickname}，${c.id} 號）`).join('、')}
            ——未登入讀不到內容，但那是相中人的帳號。連同莎莎，即是有兩位當事人自己在帖文下留言：她們在場，是事實，不是辨識結果。
          </p>
        </div>

        <div className="flex flex-col gap-4">
          <h2 className="font-kai text-[20px] leading-tight text-carbon-deep">人手 vs 機器</h2>

          <p className="max-w-[76ch] font-kai text-[14px] leading-relaxed text-carbon">
            名字一旦有了，同一場就可以兩邊對照：人認得的九位，管線能不能在二十三張臉裡把他們挑出來？「最高餘弦」取該位參賽者對全部二十三個框的最大值，「排名」是這個分數在九十四位之中的位置；「高於雜訊」比較的是名單以外的八十五位參賽者第
            90 百分位（<span className="font-mono tabular-nums">{ROSTER_NOISE.p90.toFixed(3)}</span>
            ）——過了這條線，分數才算有可能是這個人而不是任何人。
          </p>

          <Card padding="none" className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse">
              <caption className="px-3 py-2 text-left font-kai text-[13px] text-carbon-soft">
                看過節目的人認得的參賽者 · 對二十三個框的最高餘弦
              </caption>
              <thead>
                <tr className="font-kai text-[12px] text-ink-muted">
                  <th className={CELL}>編號</th>
                  <th className={CELL}>暱稱</th>
                  <th className={CELL}>姓名</th>
                  <th className={CELL}>最高餘弦</th>
                  <th className={CELL}>排名</th>
                  <th className={CELL}>出分框</th>
                  <th className={CELL}>高於雜訊</th>
                </tr>
              </thead>
              <tbody>
                {NAMED_PRESENT.map((c) => (
                  <tr key={c.id} className="hover:bg-tint">
                    <td className={`${CELL} ${NUM} text-carbon-soft`}>{c.id}</td>
                    <td className={`${CELL} font-kai text-[13px] text-carbon-deep`}>
                      {c.nickname}
                      {c.maybe ? (
                        <span className="ml-2 font-kai text-[11px] text-ink-muted">未確定</span>
                      ) : null}
                    </td>
                    <td className={`${CELL} font-kai text-[13px] text-carbon-soft`}>{c.name}</td>
                    <td className={`${CELL} ${NUM} text-carbon-deep`}>{c.best.toFixed(3)}</td>
                    <td className={`${CELL} ${NUM} text-carbon-soft`}>{c.rank}/94</td>
                    <td className={`${CELL} text-ink-muted`}>
                      {/* The frame's 一/二 is set in 楷; JetBrains Mono draws 一 as an em dash. */}
                      <span className="font-kai text-[13px]">圖{c.face.slice(0, 1)}</span>{' '}
                      <span className={NUM}>#{c.face.slice(2)}</span>{' '}
                      <span className={`${NUM} text-carbon-soft`}>
                        {c.px[0]}×{c.px[1]}
                      </span>
                    </td>
                    <td className={CELL}>
                      <Stamp tone={c.aboveNoise ? 'carbon' : 'muted'}>
                        {c.aboveNoise ? '是' : '否'}
                      </Stamp>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <div className="flex max-w-[76ch] flex-col gap-3 font-kai text-[14px] leading-relaxed text-carbon">
            <p>
              九位之中只有三位過了雜訊線：暐翹 <span className="font-mono text-[13px]">0.388</span>
              （第 1）、Carina <span className="font-mono text-[13px]">0.325</span>（第 3）、何佩{' '}
              <span className="font-mono text-[13px]">0.264</span>（第 6）。其餘六位落在{' '}
              <span className="font-mono text-[13px]">0.186</span>–
              <span className="font-mono text-[13px]">0.220</span>
              ，與沒有提及的八十五位（平均{' '}
              <span className="font-mono tabular-nums">{ROSTER_NOISE.mean.toFixed(3)}</span>
              ）分不開。Ivy So 更低到 <span className="font-mono text-[13px]">0.111</span>
              、第九十名——若她真在框內，管線對她等於全無訊號。
            </p>
            <p>
              最硬的一組對照是莎莎與蘇菲：兩人在帖文下親自回覆，在場無可爭議；系統給莎莎{' '}
              <span className="font-mono text-[13px]">0.206</span>（第 28）、蘇菲{' '}
              <span className="font-mono text-[13px]">0.207</span>（第 26），兩個都在雜訊線 0.231
              之下。人在場，分數卻落在「誰都可能」的區間——低分不能讀成「唔在場」。
            </p>
            <p>
              差別在人眼的先驗：看過整個節目的人，靠髮型、身形、衣着與同行名單，在 14×19
              像素上也能認人；ArcFace
              只看那幾十個像素之間的向量角度。同一個場景，一邊是全中，一邊是三位半。
            </p>
            <p>
              上面九位只是認得的部分——其餘兩位認不出，也可能有未列出來的參賽者。所以要另一邊試：把名單全部拿掉，讓管線自己在九十四位裡挑。
              {OPEN_TOP1.boxes} 個框的 top-1 落在{' '}
              <span className="font-mono text-[13px]">{OPEN_TOP1.distinct}</span> 位不同參賽者身上（
              {OPEN_TOP1.repeated.map((r, i) => (
                <span key={r.nickname}>
                  {i > 0 ? '、' : ''}
                  {r.nickname}
                  {r.times > 2 ? ` ×${r.times}` : ''}
                </span>
              ))}
              ）。十一個人左右的隊，機器認出十幾個人，而且同一位被認到三處不同位置——多出來的就是噪聲。所以這一頁不逐框標名。
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <h2 className="font-kai text-[20px] leading-tight text-carbon-deep">原圖 12 MP</h2>

          <p className="max-w-[76ch] font-kai text-[14px] leading-relaxed text-carbon">
            帖文其實有三張相，而且第一張可以取回原檔：{HIRES_COMPARISON.original.width}×
            {Math.round((HIRES_COMPARISON.original.width * 3) / 4)}
            ，是這一頁所用截圖的{' '}
            {(HIRES_COMPARISON.original.width / HIRES_COMPARISON.paste.width).toFixed(1)}
            倍闊，臉由 {HIRES_COMPARISON.paste.face[0]}×{HIRES_COMPARISON.paste.face[1]} 變成{' '}
            {HIRES_COMPARISON.original.face[0]}×{HIRES_COMPARISON.original.face[1]}{' '}
            像素。同一批臉、同一套參考向量，重跑一次：
          </p>

          <Card padding="none" className="max-w-[560px] overflow-x-auto">
            <table className="w-full border-collapse">
              <caption className="px-3 py-2 text-left font-kai text-[13px] text-carbon-soft">
                同一張相、兩個解像度 · 最高餘弦
              </caption>
              <thead>
                <tr className="font-kai text-[12px] text-ink-muted">
                  <th className={CELL}>參賽者</th>
                  <th className={CELL}>1085 px 截圖</th>
                  <th className={CELL}>4032 px 原檔</th>
                  <th className={CELL}>差</th>
                </tr>
              </thead>
              <tbody>
                {HIRES_COMPARISON.rows.map((r) => (
                  <tr key={r.nickname} className="hover:bg-tint">
                    <td className={`${CELL} font-kai text-[13px] text-carbon-deep`}>
                      {r.nickname}
                    </td>
                    <td className={`${CELL} ${NUM} text-carbon-soft`}>{r.paste.toFixed(3)}</td>
                    <td className={`${CELL} ${NUM} text-carbon`}>{r.original.toFixed(3)}</td>
                    <td className={`${CELL} ${NUM} text-ink-muted`}>
                      {(r.original - r.paste >= 0 ? '+' : '') + (r.original - r.paste).toFixed(3)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <div className="flex max-w-[76ch] flex-col gap-3 font-kai text-[14px] leading-relaxed text-carbon">
            <p>
              兩邊的分數幾乎一樣：暐翹 <span className="font-mono text-[13px]">0.388 → 0.392</span>
              ，Carina <span className="font-mono text-[13px]">0.325 → 0.325</span>
              ，相差不到半個百分點。換句話說，之前把低分歸咎於像素太少，是錯的推論：臉由 35×44
              放大到
              136×167，向量幾乎不動。真正的限制在參考集與現場——妝、光、角度、遮擋——不是解像度。
            </p>
            <p>
              何佩反而由 0.264 跌到 0.227，因為 12 MP
              之下偵測框落在另一個位置，同一個人被切得不同。框位與姿態帶來的波動（±0.04）比解像度帶來的增益（≤0.005）更大——所以「換張靚相再試」不會令結果穩定。
            </p>
            <p>
              三張相之中，只有第一張能取回原檔；第二、三張對未登入的讀者只派
              640×480，分格之後見到的臉只有八至十六像素，最高餘弦 0.240–0.304，全在雜訊之內。
            </p>
          </div>

          <Card padding="none" className="max-w-[560px] overflow-x-auto">
            <table className="w-full border-collapse">
              <caption className="px-3 py-2 text-left font-kai text-[13px] text-carbon-soft">
                帖文三張相 · 拿到的解像度與結果
              </caption>
              <thead>
                <tr className="font-kai text-[12px] text-ink-muted">
                  <th className={CELL}>相片</th>
                  <th className={CELL}>取得解像度</th>
                  <th className={CELL}>人臉</th>
                  <th className={CELL}>臉闊</th>
                  <th className={CELL}>最高餘弦</th>
                </tr>
              </thead>
              <tbody>
                {POST_PHOTOS.map((p) => (
                  <tr key={p.n} className="hover:bg-tint">
                    <td className={`${CELL} ${NUM} text-carbon-soft`}>{p.n}</td>
                    <td className={`${CELL} ${NUM} text-carbon`}>{p.served}</td>
                    <td className={`${CELL} ${NUM} text-carbon-soft`}>{p.faces}</td>
                    <td className={`${CELL} ${NUM} text-ink-muted`}>{p.facePx} px</td>
                    <td className={`${CELL} ${NUM} text-carbon-deep`}>{p.best.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>

        <div className="flex flex-col gap-4">
          <h2 className="font-kai text-[20px] leading-tight text-carbon-deep">門檻的代價</h2>

          <div className="flex max-w-[76ch] flex-col gap-3 font-kai text-[14px] leading-relaxed text-carbon">
            <p>
              同一個檢驗，貼到不同的門檻上：638
              個參考向量，每個對齊「其他參賽者」的最高分，數有多少個會因此被認錯人。
            </p>
          </div>

          <Card padding="none" className="max-w-[560px] overflow-x-auto">
            <table className="w-full border-collapse">
              <caption className="px-3 py-2 text-left font-kai text-[13px] text-carbon-soft">
                門檻 vs 假配對率 · 638 個參考向量
              </caption>
              <thead>
                <tr className="font-kai text-[12px] text-ink-muted">
                  <th className={CELL}>門檻</th>
                  <th className={CELL}>錯配陌生人</th>
                  <th className={CELL}>本批過檻</th>
                  <th className={CELL}>相對</th>
                </tr>
              </thead>
              <tbody>
                {CUTOFF_SWEEP.map((row) => {
                  const isJob = row.cutoff === JOB_THRESHOLD;
                  const isSite = row.cutoff === SITE_THRESHOLD;
                  return (
                    <tr
                      key={row.cutoff}
                      className={isJob ? 'bg-stamp/5 font-bold' : 'hover:bg-tint'}
                    >
                      <td className={`${CELL} ${NUM} text-carbon-deep`}>
                        {row.cutoff.toFixed(3)}
                        {isSite ? (
                          <span className="ml-2 font-kai text-[11px] font-normal text-ink-muted">
                            本站
                          </span>
                        ) : null}
                        {isJob ? (
                          <span className="ml-2 font-kai text-[11px] font-normal text-stamp">
                            本頁
                          </span>
                        ) : null}
                      </td>
                      <td className={`${CELL} ${NUM} text-carbon`}>
                        {(row.rate * 100).toFixed(1)}%
                      </td>
                      <td className={`${CELL} ${NUM} text-carbon-soft`}>
                        {
                          STREET_IMAGES.flatMap((im) => im.faces).filter(
                            (f) => f.top1 >= row.cutoff,
                          ).length
                        }
                      </td>
                      <td className={`${CELL} flex flex-col justify-center`}>
                        <span
                          aria-hidden="true"
                          className="block h-[6px] rounded-xs bg-carbon-deep/25"
                          style={{ width: `${Math.min(100, row.rate * 100)}%` }}
                        />
                        <span className="sr-only">{(row.rate * 100).toFixed(1)}%</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>

          <div className="flex max-w-[76ch] flex-col gap-3 font-kai text-[14px] leading-relaxed text-carbon">
            <p>
              0.30
              會多放出三個名字，代價是接近一半的參考向量都會錯配陌生人——那樣的名單等於抽籤。0.35
              只剩一個，錯配率約一成，仍是「候選」而不是「認定」。
            </p>
            <p>
              為何分數普遍偏低，要看像素本身。第二張在原生解像度下一個框都不出：臉只有 14×19
              像素，低於 <span className="font-mono text-[13px]">min_face_size: 20</span>
              ，偵測器把每一張都丟掉。以 4× 分格重跑才有十個框——分格救回的是「偵測」，不是「資訊」。
            </p>
            <p>
              餘弦是 512
              維向量之間的角度，而向量由那幾十個像素擬出來。同一張臉壓到不同高度再抽一次向量，與原生向量的相似度如下：
            </p>
          </div>

          <Card padding="none" className="max-w-[560px] overflow-x-auto">
            <table className="w-full border-collapse">
              <caption className="px-3 py-2 text-left font-kai text-[13px] text-carbon-soft">
                同一張臉降採樣後的自相似度 · 9 張臉取平均
              </caption>
              <thead>
                <tr className="font-kai text-[12px] text-ink-muted">
                  <th className={CELL}>臉高</th>
                  <th className={CELL}>平均餘弦</th>
                  <th className={CELL}>最差</th>
                  <th className={CELL}>餘弦相對原生</th>
                </tr>
              </thead>
              <tbody>
                {FACE_SIZE_CEILING.map((r) => (
                  <tr key={r.height} className="hover:bg-tint">
                    <td className={`${CELL} ${NUM} text-carbon-deep`}>{r.height} px</td>
                    <td className={`${CELL} ${NUM} text-carbon`}>{r.mean.toFixed(3)}</td>
                    <td className={`${CELL} ${NUM} text-ink-muted`}>{r.min.toFixed(3)}</td>
                    <td className={`${CELL} flex flex-col justify-center`}>
                      <span
                        aria-hidden="true"
                        className="block h-[6px] rounded-xs bg-carbon-deep/25"
                        style={{ width: `${Math.max(0, (r.mean - 0.5) / 0.5) * 100}%` }}
                      />
                      <span className="sr-only">{r.mean.toFixed(3)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <div className="flex max-w-[76ch] flex-col gap-3 font-kai text-[14px] leading-relaxed text-carbon">
            <p>
              街拍裡的臉高 18–20 像素：單是這一步，同一個人同一個框就已經掉到{' '}
              <span className="font-mono text-[13px]">0.79</span>
              。真正配對（genuine，留下自己的另一張相）平均 {MATCHER_CHECK.genuineMean.toFixed(
                3,
              )}，{' '}
              {(MATCHER_CHECK.genuineAboveThreshold * 100).toFixed(0)}% 過本站門檻；假配對在{' '}
              {MATCHER_CHECK.impostorMax.toFixed(3)}{' '}
              封頂。兩個分佈本來就貼得很近，再扣掉降採樣那一截，剩下的差距不足以下判斷。
            </p>
            <p>
              但要講清楚因果：降採樣是加劇因素，不是主因。上面「原圖 12
              MP」一節把同一張相的原檔跑了一次——臉放大四倍，分數只動了
              0.004。低分的來源是參考集與現場條件的落差，換張大相解決不了。
            </p>
            <p>
              其他未過檻的框，首兩位相差由{' '}
              <span className="font-mono text-[13px]">{TOTALS.tightestMargin.toFixed(3)}</span> 到{' '}
              <span className="font-mono text-[13px]">{TOTALS.widestMargin.toFixed(3)}</span>
              ，排第一與排第二的距離落在噪聲之內，所以不列名字。
            </p>
          </div>
        </div>

        <div className="mt-2 flex max-w-[76ch] flex-col gap-1 border-t border-carbon-deep/13 pt-3 font-kai text-[12px] leading-relaxed text-ink-muted">
          <span>
            方法：InsightFace buffalo_l（detection + recognition），
            <span className="font-mono">det_size</span> 640（第二張分格 4×）·{' '}
            <span className="font-mono">min_face_size</span> 20 · {REFERENCE_COUNT} 個參考向量 /{' '}
            {CONTESTANT_COUNT} 位參賽者 · 配對取每個參賽者參考集的最大餘弦 · 本頁門檻{' '}
            <span className="font-mono">{JOB_THRESHOLD.toFixed(3)}</span>（本站預設{' '}
            <span className="font-mono">{SITE_THRESHOLD.toFixed(3)}</span>，未改動）。
          </span>
          <span>
            相片來源：
            <a
              href="https://www.threads.com/@zisha_1001/post/DfuWFhMH-4X"
              target="_blank"
              rel="noreferrer noopener"
              className="underline decoration-carbon-deep/30 underline-offset-2 hover:decoration-carbon-deep"
            >
              Threads · @zisha_1001
            </a>
            （路人拍攝，非《全民造星 IV》官方素材）；名單由看過節目的觀眾對照 超酸 IG story
            認人，非系統推斷。框的位置以幀比例存，乘以顯示尺寸即為像素位置。
          </span>
        </div>
      </div>
    </div>
  );
}
