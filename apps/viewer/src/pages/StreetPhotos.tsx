import { Link } from 'react-router';
import { Card, Masthead, Stamp, bandFor, buttonClasses } from '@mv/shared';
import {
  CONTESTANT_COUNT,
  CUTOFF_SWEEP,
  FACE_SIZE_CEILING,
  RESOLUTION_LADDER,
  JOB_THRESHOLD,
  MATCHER_CHECK,
  NAMED_PRESENT,
  OPEN_TOP1,
  POSED_FRAME,
  POST_PHOTOS,
  POST_REPLIES,
  REPORTED_REPLY_AUTHORS,
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

/**
 * The worker serves this exact string in the `/street` document head (`ROUTE_HEADS`) so a shared
 * link unfurls with it; the browser tab must not contradict what the link promised.
 */
const CELL = 'border-b border-carbon-deep/13 px-2 py-1.5 text-left align-baseline';
const NUM = 'font-mono text-[13px] tabular-nums';

function Figure({ image }: { image: StreetImage }) {
  // A frame can hold zero faces (it is what the queuing shot does at native resolution), so the
  // seed is the first face only when there is one.
  const best = image.faces.length ? image.faces.reduce((a, f) => (f.top1 > a.top1 ? f : a)) : null;
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
              <span className="absolute -top-[16px] left-0 font-mono text-[12px] leading-none text-carbon-deep">
                {face.i}
              </span>
            </span>
          );
        })}
      </div>
      <figcaption className="flex flex-col gap-1 font-kai text-[13px] leading-relaxed text-carbon-soft">
        <span>{image.caption}</span>
        <span className="font-mono text-[12px] tabular-nums text-ink-muted">
          {image.faces.length} 框
          {best ? (
            <>
              {' · 最高 '}
              {best.top1.toFixed(3)}
              {' · 距本站門檻 '}
              {(SITE_THRESHOLD - best.top1).toFixed(3)}
            </>
          ) : null}
        </span>
      </figcaption>
    </figure>
  );
}

export function StreetPhotos() {
  const bestCandidate = STREET_IMAGES.flatMap((im) =>
    im.faces.map((face) => ({ face, image: im })),
  ).find((r) => r.face.candidate);
  const jobRate = CUTOFF_SWEEP.find((r) => r.cutoff === JOB_THRESHOLD)?.rate ?? 0;
  const named = NAMED_PRESENT.filter((c) => !c.maybe);
  const clearsNoise = named.filter((c) => c.aboveNoise);
  const belowNoise = named.filter((c) => !c.aboveNoise);
  const byId = (id: string) => NAMED_PRESENT.find((c) => c.id === id)!;
  const ivy = byId('1');
  const sasa = byId('5');
  const sophie = byId('18');

  return (
    // The root stays a plain block: as a `flex-1` column it hands its children a definite height,
    // and they shrink into it — the tables would collapse to their borders.
    <div className="min-h-full flex-1">
      <div className="flex flex-col gap-6 px-4 pb-10 pt-6 sm:px-14 sm:pt-8">
        <Masthead title="街拍" hint="場外兩張 · 人手認得九位 · 機器認得一位">
          <span className="font-mono text-[12px] tabular-nums">2026-11-15</span>
          <Stamp tone="muted">唯讀</Stamp>
        </Masthead>

        {/* Arrival block: most readers come from a link on the original Threads post, asking what
            this group is. Answer that first, then route them into the site proper. */}
        <div className="flex flex-col gap-3 rounded-md border border-stamp/40 bg-stamp/5 p-4 sm:p-5">
          <span className="font-kai text-[13px] font-bold tracking-wide text-stamp">答案</span>
          <p className="font-kai text-[18px] leading-snug text-carbon-deep sm:text-[28px]">
            銅鑼灣那一隊「疑似女團」，是《全民造星 IV》的參賽者——2021 年那一屆，96 位。
          </p>
          <p className="max-w-[68ch] font-kai text-[14px] leading-relaxed text-carbon">
            帖文下面兩種答法都對：其中 Carina（李晞彤）與 Ada（姜咏鑫）已於 2024 年以英皇女團 VIVA
            出道，所以「造星 IV」與「VIVA 拍 MV」說的是同一批人。
          </p>
          <p className="max-w-[68ch] font-kai text-[14px] leading-relaxed text-carbon">
            這個站用同一套臉部辨識，把《前傳》三部曲等 MV 逐格認人：每個框對過 {REFERENCE_COUNT}{' '}
            個參考向量，分數是原始餘弦，逐條可以覆核。下面是我拿這幾張街拍去跑的結果，最後一節講為什麼人眼一望就認得、機器卻幾乎認不出。
          </p>
          {/* Real links, not buttons: a funnel's exits must open in a new tab and be crawlable. */}
          <div className="flex flex-row flex-wrap gap-2">
            <Link to="/" className={buttonClasses({ variant: 'primary', size: 'lg' })}>
              入去點唱單
            </Link>
            <Link to="/cast" className={buttonClasses({ size: 'lg' })}>
              睇名冊
            </Link>
            <Link to="/analytics" className={buttonClasses({ size: 'lg' })}>
              睇辨識紀錄
            </Link>
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
          的參考向量會錯配陌生人。{TOTALS.faces} 個框之中，只有 {TOTALS.accepted} 個過檻。
        </p>

        {bestCandidate?.face.candidate && (
          <Card padding="md" className="flex max-w-[68ch] flex-col gap-2 border-stamp/40">
            <div className="flex flex-row flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="font-kai text-[13px] text-carbon-soft">
                {bestCandidate.image.key === 'a' ? '一 · 過路' : '二 · 排隊'} 第{' '}
                {bestCandidate.face.i} 個框
              </span>
              <span className="font-kai text-[18px] leading-tight text-carbon-deep">
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
              候選，不是認定。這一格是全批最闊的差距（
              <span className={NUM}>{TOTALS.widestMargin.toFixed(3)}</span>
              ），但仍低於本站接受門檻 <span className={NUM}>{SITE_THRESHOLD.toFixed(3)}</span>
              ，差{' '}
              <span className={NUM}>{(SITE_THRESHOLD - bestCandidate.face.top1).toFixed(3)}</span>
              ——本站的定義裡，未過門檻的不叫辨識。它之所以列出來，只因為本頁把門檻降到{' '}
              <span className={NUM}>{JOB_THRESHOLD.toFixed(3)}</span>，而那條線有約{' '}
              {((CUTOFF_SWEEP.find((r) => r.cutoff === JOB_THRESHOLD)?.rate ?? 0) * 100).toFixed(0)}
              % 的錯配率。
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
              逐框判讀 · 1085 px 截圖 · det_size 640 · 餘弦為原始 cosine · 只有過檻的框列候選
            </caption>
            <thead>
              <tr className="font-kai text-[12px] text-ink-muted">
                <th scope="col" className={CELL}>
                  圖
                </th>
                <th scope="col" className={CELL}>
                  #
                </th>
                <th scope="col" className={CELL}>
                  框（像素）
                </th>
                <th scope="col" className={CELL}>
                  偵測分
                </th>
                <th scope="col" className={CELL}>
                  最高餘弦
                </th>
                <th scope="col" className={CELL}>
                  次高
                </th>
                <th scope="col" className={CELL}>
                  相差
                </th>
                <th scope="col" className={CELL}>
                  候選
                </th>
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
          <h2 className="font-kai text-[18px] leading-tight text-carbon-deep">另一張：正面合照</h2>

          <p className="max-w-[76ch] font-kai text-[14px] leading-relaxed text-carbon">
            同一位樓主後來貼了另一張：十一人排排企、正面、有補光。同一套向量庫、同一個門檻，這一張有{' '}
            <span className={NUM}>{POSED_FRAME.faces.length}</span> 張臉，其中{' '}
            <span className={NUM}>{POSED_FRAME.recognitionCount}</span> 位過本站門檻（0.412），另有{' '}
            <span className={NUM}>{POSED_FRAME.candidateCount - POSED_FRAME.recognitionCount}</span>{' '}
            位過本頁的 0.35。臉依然只是 29–41 像素——跟上面那張行走中的相差不多大。
          </p>

          <figure className="relative overflow-hidden rounded-md border border-carbon-deep/13 bg-tint">
            <img
              src="/videos/reports/street-photos-2026-11-15/posed.jpg"
              alt="正面合照：十一人排排企，逐個框出面孔"
              width={POSED_FRAME.width}
              height={POSED_FRAME.height}
              loading="lazy"
              className="block w-full"
            />
            {POSED_FRAME.faces.map((face) => {
              const [x1, y1, x2, y2] = face.box;
              return (
                <span
                  key={face.i}
                  aria-hidden="true"
                  className={`pointer-events-none absolute border ${
                    face.verdict === 'recognition'
                      ? 'border-2 border-carbon-deep'
                      : 'border border-carbon-deep/60'
                  }`}
                  style={{
                    left: `${x1 * 100}%`,
                    top: `${y1 * 100}%`,
                    width: `${(x2 - x1) * 100}%`,
                    height: `${(y2 - y1) * 100}%`,
                  }}
                >
                  <span className="absolute -top-[16px] left-0 font-mono text-[12px] leading-none text-carbon-deep">
                    {face.i}
                  </span>
                </span>
              );
            })}
          </figure>

          <Card padding="none" className="max-w-[720px] overflow-x-auto">
            <table className="w-full border-collapse">
              <caption className="px-3 py-2 text-left font-kai text-[13px] text-carbon-soft">
                正面合照 · 逐臉最高餘弦（{POSED_FRAME.width}×{POSED_FRAME.height}，det_size 640）
              </caption>
              <thead>
                <tr className="font-kai text-[12px] text-ink-muted">
                  <th scope="col" className={CELL}>
                    #
                  </th>
                  <th scope="col" className={CELL}>
                    框（像素）
                  </th>
                  <th scope="col" className={CELL}>
                    最高餘弦
                  </th>
                  <th scope="col" className={CELL}>
                    最佳候選
                  </th>
                  <th scope="col" className={CELL}>
                    判定
                  </th>
                </tr>
              </thead>
              <tbody>
                {POSED_FRAME.faces.map((face) => (
                  <tr
                    key={face.i}
                    className={face.verdict === 'recognition' ? 'bg-stamp/5' : 'hover:bg-tint'}
                  >
                    <td className={`${CELL} ${NUM} text-carbon-soft`}>{face.i}</td>
                    <td className={`${CELL} ${NUM} text-carbon-soft`}>
                      {face.px[0]}×{face.px[1]}
                    </td>
                    <td className={`${CELL} ${NUM} text-carbon-deep`}>{face.score.toFixed(3)}</td>
                    <td className={`${CELL} font-kai text-[13px] text-carbon`}>
                      {face.nickname}
                      <span className="ml-2 font-mono text-[12px] text-ink-muted">{face.id}</span>
                    </td>
                    <td className={CELL}>
                      {face.verdict === 'recognition' ? (
                        <Stamp tone="carbon">認定</Stamp>
                      ) : face.verdict === 'candidate' ? (
                        <Stamp band="low">候選</Stamp>
                      ) : (
                        <span className="font-kai text-[12px] text-ink-muted">未過檻</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <div className="flex max-w-[76ch] flex-col gap-3 font-kai text-[14px] leading-relaxed text-carbon">
            <p>
              第一位是 {POSED_FRAME.faces.find((f) => f.verdict === 'recognition')?.nickname}（
              <span className={NUM}>
                {POSED_FRAME.faces.find((f) => f.verdict === 'recognition')?.score.toFixed(3)}
              </span>
              ），全頁唯一過本站門檻的一格——而它的臉只有 32×41 像素，比上面行走那張的 36×44
              還要細。像素多少不是關鍵：正面、無遮擋、光線夠，同一個人在同一套向量下可以由 0.267
              升到 0.456。
            </p>
            <p>
              更值得看的是順序：這十一格的最佳候選，左至右很大程度對得上帖文裡逐個認人的次序（Karen、暐翹、何佩、咖喱、Ada、Carina、莎莎……蘇菲）。單格分數未過檻不等於認錯人，只是證據不足以下一個「認定」——所以只有一格標認定，其餘標候選或未過檻。
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <h2 className="font-kai text-[18px] leading-tight text-carbon-deep">帖文下的回覆</h2>

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
            讀者另指出，回覆之中還有{' '}
            {REPORTED_REPLY_AUTHORS.map((c) => `${c.name}（${c.nickname}，${c.id} 號）`).join('、')}
            ——未登入讀不到內容，所以這裡只記錄「有人這樣認出」，不引述。連同莎莎，即是有兩位當事人與帖文有關：這比任何餘弦都直接。
          </p>
        </div>

        <div className="flex flex-col gap-4">
          <h2 className="font-kai text-[18px] leading-tight text-carbon-deep">人手 vs 機器</h2>

          <p className="max-w-[76ch] font-kai text-[14px] leading-relaxed text-carbon">
            名字一旦有了，同一場就可以兩邊對照：人認得的九位，管線能不能在 {TOTALS.faces}{' '}
            張臉裡把他們挑出來？「最高餘弦」取該位參賽者對全部 {TOTALS.faces}{' '}
            個框的最大值，「排名」是這個分數在 {CONTESTANT_COUNT}{' '}
            位之中的位置；「高於雜訊」比較的是名單以外的 {CONTESTANT_COUNT - 9} 位參賽者第 90
            百分位（<span className="font-mono tabular-nums">{ROSTER_NOISE.p90.toFixed(3)}</span>
            ）——過了這條線，分數才算有可能是這個人而不是任何人。
          </p>

          <Card padding="none" className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse">
              <caption className="px-3 py-2 text-left font-kai text-[13px] text-carbon-soft">
                看過節目的人認得的參賽者 · 對 {TOTALS.faces} 個框的最高餘弦（1085 px 截圖，同一輪）
              </caption>
              <thead>
                <tr className="font-kai text-[12px] text-ink-muted">
                  <th scope="col" className={CELL}>
                    編號
                  </th>
                  <th scope="col" className={CELL}>
                    暱稱
                  </th>
                  <th scope="col" className={CELL}>
                    姓名
                  </th>
                  <th scope="col" className={CELL}>
                    最高餘弦
                  </th>
                  <th scope="col" className={CELL}>
                    排名
                  </th>
                  <th scope="col" className={CELL}>
                    出分框
                  </th>
                  <th scope="col" className={CELL}>
                    高於雜訊
                  </th>
                </tr>
              </thead>
              <tbody>
                {NAMED_PRESENT.map((c) => (
                  <tr key={c.id} className="hover:bg-tint">
                    <td className={`${CELL} ${NUM} text-carbon-soft`}>{c.id}</td>
                    <td className={`${CELL} font-kai text-[13px] text-carbon-deep`}>
                      {c.nickname}
                      {c.maybe ? (
                        <span className="ml-2 font-kai text-[12px] text-ink-muted">未確定</span>
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
              認得的九位之中，過了雜訊線的有 {clearsNoise.length} 位：
              {clearsNoise.map((c, index) => (
                <span key={c.id}>
                  {index > 0 ? '、' : ''}
                  {c.nickname} <span className={NUM}>{c.best.toFixed(3)}</span>（第 {c.rank}）
                </span>
              ))}
              。其餘 {belowNoise.length} 位落在{' '}
              <span className={NUM}>{Math.min(...belowNoise.map((c) => c.best)).toFixed(3)}</span>–
              <span className={NUM}>{Math.max(...belowNoise.map((c) => c.best)).toFixed(3)}</span>
              ，與名單以外的 {CONTESTANT_COUNT - named.length} 位（平均{' '}
              <span className={NUM}>{ROSTER_NOISE.mean.toFixed(3)}</span>
              ）分不開。Ivy So 更低到 <span className={NUM}>{ivy.best.toFixed(3)}</span>
              、第 {ivy.rank} 名——若她真在框內，管線對她等於全無訊號。
            </p>
            <p>
              最硬的一組對照是莎莎與蘇菲。莎莎的帳號在帖文下親自回覆，蘇菲亦有回覆（讀者指出，見上節）；兩人在場毋庸置疑，而系統給莎莎{' '}
              <span className={NUM}>{sasa.best.toFixed(3)}</span>（第 {sasa.rank}）、蘇菲{' '}
              <span className={NUM}>{sophie.best.toFixed(3)}</span>（第 {sophie.rank}
              ），都在雜訊線 <span className={NUM}>{ROSTER_NOISE.p90.toFixed(3)}</span>
              之下。人在場，分數卻落在「誰都可能」的區間——低分不能讀成「唔在場」。
            </p>
            <p>
              差別在人眼的先驗：看過整個節目的人，靠髮型、身形、衣着與同行名單，在 14×19
              像素上也能認人；ArcFace
              只看那幾十個像素之間的向量角度。同一個場景，一邊是全中，一邊是三位半。
            </p>
            <p>
              上面九位只是認得的部分——其餘兩位認不出，也可能有未列出來的參賽者。所以要另一邊試：把名單全部拿掉，讓管線自己在{' '}
              {CONTESTANT_COUNT} 位裡挑。
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
          <h2 className="font-kai text-[18px] leading-tight text-carbon-deep">
            同一張相、三個解像度
          </h2>

          <p className="max-w-[76ch] font-kai text-[14px] leading-relaxed text-carbon">
            同一格畫面，換過三種來源：聊天轉貼的截圖、另一個轉貼原檔、帖文原相。臉由{' '}
            {RESOLUTION_LADDER.frames[0].facePx} 變成 {RESOLUTION_LADDER.frames[2].facePx}{' '}
            像素，同一個人、同一套參考向量、同一個 det_size，重跑三次：
          </p>

          <Card padding="none" className="max-w-[640px] overflow-x-auto">
            <table className="w-full border-collapse">
              <caption className="px-3 py-2 text-left font-kai text-[13px] text-carbon-soft">
                同一張相 · 最高餘弦（三邊都以 det_size 640 偵測）
              </caption>
              <thead>
                <tr className="font-kai text-[12px] text-ink-muted">
                  <th scope="col" className={CELL}>
                    參賽者
                  </th>
                  {RESOLUTION_LADDER.frames.map((frame) => (
                    <th key={frame.label} scope="col" className={CELL}>
                      {frame.label}
                    </th>
                  ))}
                  <th scope="col" className={CELL}>
                    擺幅
                  </th>
                </tr>
              </thead>
              <tbody>
                {RESOLUTION_LADDER.rows.map((row) => (
                  <tr key={row.nickname} className="hover:bg-tint">
                    <td className={`${CELL} font-kai text-[13px] text-carbon-deep`}>
                      {row.nickname}
                    </td>
                    {row.scores.map((score, index) => (
                      <td
                        key={RESOLUTION_LADDER.frames[index].label}
                        className={`${CELL} ${NUM} ${
                          index === 1 ? 'text-carbon-soft' : 'text-carbon'
                        }`}
                      >
                        {score.toFixed(3)}
                      </td>
                    ))}
                    <td className={`${CELL} ${NUM} text-ink-muted`}>
                      {(Math.max(...row.scores) - Math.min(...row.scores)).toFixed(3)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <div className="flex max-w-[76ch] flex-col gap-3 font-kai text-[14px] leading-relaxed text-carbon">
            <p>
              {RESOLUTION_LADDER.rows
                .filter((row) => Math.max(...row.scores) - Math.min(...row.scores) <= 0.02)
                .map((row) => row.nickname)
                .join('、')}
              的擺幅在 0.02
              以內——臉放大十幾倍，向量幾乎不動。所以「低分因為像素太少」是錯的推論：真正的限制在參考集與現場（妝、光、角度、遮擋）。
            </p>
            <p>
              其餘兩位擺幅更大，但方向不一致：同一個人在三張圖上被切在不同的框位，分數跟框走而不是跟解像度走。框位與姿態帶來的波動，比解像度帶來的增益大一個數量級——「換張靚相再試」不會令結果穩定。
            </p>
            <p>
              {RESOLUTION_LADDER.frames
                .map((frame) => `${frame.label}偵測到 ${frame.faces} 張臉`)
                .join('、')}
              ；臉的大小差異，就是三邊分數差異的全部來源。
            </p>
          </div>

          <Card padding="none" className="max-w-[560px] overflow-x-auto">
            <table className="w-full border-collapse">
              <caption className="px-3 py-2 text-left font-kai text-[13px] text-carbon-soft">
                帖文三張相 · 拿到的解像度與結果
              </caption>
              <thead>
                <tr className="font-kai text-[12px] text-ink-muted">
                  <th scope="col" className={CELL}>
                    相片
                  </th>
                  <th scope="col" className={CELL}>
                    取得解像度
                  </th>
                  <th scope="col" className={CELL}>
                    人臉
                  </th>
                  <th scope="col" className={CELL}>
                    臉闊
                  </th>
                  <th scope="col" className={CELL}>
                    最高餘弦
                  </th>
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
          <h2 className="font-kai text-[18px] leading-tight text-carbon-deep">門檻的代價</h2>

          <div className="flex max-w-[76ch] flex-col gap-3 font-kai text-[14px] leading-relaxed text-carbon">
            <p>
              同一個檢驗，貼到不同的門檻上：{REFERENCE_COUNT}
              個參考向量，每個對齊「其他參賽者」的最高分，數有多少個會因此被認錯人。
            </p>
          </div>

          <Card padding="none" className="max-w-[560px] overflow-x-auto">
            <table className="w-full border-collapse">
              <caption className="px-3 py-2 text-left font-kai text-[13px] text-carbon-soft">
                門檻 vs 假配對率 · {REFERENCE_COUNT} 個參考向量
              </caption>
              <thead>
                <tr className="font-kai text-[12px] text-ink-muted">
                  <th scope="col" className={CELL}>
                    門檻
                  </th>
                  <th scope="col" className={CELL}>
                    錯配陌生人
                  </th>
                  <th scope="col" className={CELL}>
                    本批過檻
                  </th>
                  <th scope="col" className={CELL}>
                    相對
                  </th>
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
                          <span className="ml-2 font-kai text-[12px] font-normal text-ink-muted">
                            本站
                          </span>
                        ) : null}
                        {isJob ? (
                          <span className="ml-2 font-kai text-[12px] font-normal text-stamp">
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
              {(() => {
                const passes = (cutoff: number) =>
                  STREET_IMAGES.flatMap((image) => image.faces).filter((f) => f.top1 >= cutoff)
                    .length;
                const loosen = CUTOFF_SWEEP.find((r) => r.cutoff === 0.3)!;
                return (
                  <>
                    放寬到 <span className={NUM}>{loosen.cutoff.toFixed(2)}</span> 會多出{' '}
                    {passes(loosen.cutoff) - TOTALS.accepted} 個名字，代價是{' '}
                    <span className={NUM}>{(loosen.rate * 100).toFixed(0)}%</span>
                    的參考向量都會錯配陌生人——那樣的名單等於抽籤。守在{' '}
                    <span className={NUM}>{JOB_THRESHOLD.toFixed(2)}</span> 只剩 {TOTALS.accepted}{' '}
                    個，錯配率約 <span className={NUM}>{(jobRate * 100).toFixed(0)}%</span>
                    ，仍然只是「候選」。
                  </>
                );
              })()}
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
                  <th scope="col" className={CELL}>
                    臉高
                  </th>
                  <th scope="col" className={CELL}>
                    平均餘弦
                  </th>
                  <th scope="col" className={CELL}>
                    最差
                  </th>
                  <th scope="col" className={CELL}>
                    餘弦相對原生
                  </th>
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
              但要講清楚因果：降採樣是加劇因素，不是主因。上面「同一張相、三個解像度」一節把同一格畫面跑了三次，錨點的擺幅在
              0.02 以內。低分的來源是參考集與現場條件的落差，換張大相解決不了。
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
            相片版權屬拍攝者。來源：
            <a
              href="https://www.threads.com/@zisha_1001/post/DfuWFhMH-4X"
              target="_blank"
              rel="noreferrer noopener"
              className="underline decoration-carbon-deep/30 underline-offset-2 hover:decoration-carbon-deep"
            >
              Threads · @zisha_1001
            </a>
            （路人拍攝，非《全民造星
            IV》官方素材）。本站只為核對辨識結果而複製這兩張相，沒有其他用途；拍攝者或相中人如要移除，在
            <a
              href="https://www.threads.com/@zisha_1001/post/DfuWFhMH-4X"
              target="_blank"
              rel="noreferrer noopener"
              className="underline decoration-carbon-deep/30 underline-offset-2 hover:decoration-carbon-deep"
            >
              原帖
            </a>
            回覆一句即可，本頁會連相一併下架。四張之中，1600 px 的一張取自另一則轉貼：
            <a
              href="https://www.threads.com/@rinrinrin1666/post/DfzERn0k9HS"
              target="_blank"
              rel="noreferrer noopener"
              className="underline decoration-carbon-deep/30 underline-offset-2 hover:decoration-carbon-deep"
            >
              @rinrinrin1666
            </a>
            ，同樣可要求下架。名單由看過節目的觀眾認人，非系統推斷；框的位置以幀比例存，乘以顯示尺寸即為像素位置。
          </span>
        </div>
      </div>
    </div>
  );
}
