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
  POSED_POST,
  VIDEO_HANDLES,
  VIDEO_POST,
  VIDEO_REPORT,
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
        <Masthead title="街拍" hint="街拍、正面合照與 23 秒原片 · 同一套管線逐格試跑">
          <span className="font-mono text-[12px] tabular-nums">2026-11-15</span>
          <Stamp tone="muted">唯讀</Stamp>
        </Masthead>

        {/* Arrival block: most readers come from a link on the original Threads post, asking what
            this group is. Answer that first, then route them into the site proper. */}
        <div className="flex flex-col gap-3 rounded-md border border-stamp/40 bg-stamp/5 p-4 sm:p-5">
          <span className="font-kai text-[13px] font-bold tracking-wide text-stamp">答案</span>
          <p className="font-kai text-[18px] leading-snug text-carbon-deep sm:text-[28px]">
            銅鑼灣那一班「疑似女團」，是《全民造星 IV》的參賽者。
          </p>
          <p className="max-w-[68ch] font-kai text-[14px] leading-relaxed text-carbon">
            2021 年那一屆，總共 96 位。帖文下面有人答造星 IV，也有人認出
            VIVA，兩邊都無講錯。Carina（李晞彤）和 Ada（姜咏鑫）2024 年以英皇女團 VIVA
            出道，本來就是造星 IV 出來的。
          </p>
          <p className="max-w-[68ch] font-kai text-[14px] leading-relaxed text-carbon">
            這個站平時用來逐格辨識《前傳》三部曲等 MV，每個偵測框會對過 {REFERENCE_COUNT}{' '}
            個參考向量。這一頁把兩張路人街拍、樓主後來貼的正面合照，加上當晚拍成的 23
            秒短片一併跑過，看看同一班人換了畫面之後分別有多大。
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
          最先流傳的兩張街拍來自 Threads 帖文（
          <a
            href="https://www.threads.com/@zisha_1001/post/DfuWFhMH-4X"
            target="_blank"
            rel="noreferrer noopener"
            className="text-carbon-deep underline decoration-carbon-deep/30 underline-offset-2 hover:decoration-carbon-deep"
          >
            @zisha_1001
          </a>
          ），拍到一班人在銅鑼灣過馬路和在 Sogo 門外排隊。用本站預設的{' '}
          <span className="font-mono tabular-nums">{SITE_THRESHOLD.toFixed(3)}</span>{' '}
          門檻去跑這兩張相，{TOTALS.faces} 個框裡沒有一個過關。
        </p>

        <p className="max-w-[68ch] font-kai text-[14px] leading-relaxed text-carbon">
          下面先看把門檻放寬到{' '}
          <span className="font-mono tabular-nums">{JOB_THRESHOLD.toFixed(3)}</span> 的結果。在{' '}
          <span className="font-mono tabular-nums">{JOB_THRESHOLD.toFixed(3)}</span> 這條線上，
          {REFERENCE_COUNT} 個參考向量裡有{' '}
          <span className="font-mono tabular-nums">{(jobRate * 100).toFixed(1)}%</span>{' '}
          會錯配陌生人，而 {TOTALS.faces} 個框之中有 {TOTALS.accepted} 個過線。
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
              相差 <span className={NUM}>{TOTALS.widestMargin.toFixed(3)}</span>{' '}
              已經是全批最闊的一格，不過距離本站{' '}
              <span className={NUM}>{SITE_THRESHOLD.toFixed(3)}</span> 的線還差{' '}
              <span className={NUM}>{(SITE_THRESHOLD - bestCandidate.face.top1).toFixed(3)}</span>
              。按本站的標準它還只是候選，放上來是因為這一頁把門檻降到了{' '}
              <span className={NUM}>{JOB_THRESHOLD.toFixed(3)}</span>（約{' '}
              {((CUTOFF_SWEEP.find((r) => r.cutoff === JOB_THRESHOLD)?.rate ?? 0) * 100).toFixed(0)}
              % 錯配率）。
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

          <div className="flex max-w-[76ch] flex-col gap-1 border-l-2 border-carbon-deep/20 pl-3">
            <a
              href={POSED_POST.url}
              target="_blank"
              rel="noreferrer noopener"
              className="font-mono text-[12px] text-carbon-soft underline decoration-carbon-deep/20 underline-offset-2 hover:decoration-carbon-deep"
            >
              Threads · @{POSED_POST.handle}
            </a>
            <span className="whitespace-pre-line font-kai text-[14px] leading-relaxed text-carbon">
              {POSED_POST.caption}
            </span>
          </div>

          <p className="max-w-[76ch] font-kai text-[14px] leading-relaxed text-carbon">
            同一位樓主後來補多了一張合照，十一人排排企望鏡頭，有街燈和補光。臉一樣只有 29 至 41
            像素闊，跟上面過馬路那一張差不多，不過換成這張之後，
            <span className={NUM}>{POSED_FRAME.faces.length}</span> 個框裡有{' '}
            <span className={NUM}>{POSED_FRAME.recognitionCount}</span> 位過了{' '}
            <span className={NUM}>{SITE_THRESHOLD.toFixed(3)}</span>，另有{' '}
            <span className={NUM}>{POSED_FRAME.candidateCount - POSED_FRAME.recognitionCount}</span>{' '}
            位過到 <span className={NUM}>{JOB_THRESHOLD.toFixed(3)}</span>。
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
                      <span className="ml-2 font-mono text-[12px] text-ink-muted">#{face.id}</span>
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
              過了 {SITE_THRESHOLD.toFixed(3)} 的是{' '}
              {POSED_FRAME.faces.find((f) => f.verdict === 'recognition')?.nickname}（
              <span className={NUM}>
                {POSED_FRAME.faces.find((f) => f.verdict === 'recognition')?.score.toFixed(3)}
              </span>
              ），也是整批靜態相片裡唯一達標的一格。她的框只有 32×41 像素，比上面過馬路那一張的
              36×44
              還要細，可見這張認得出，靠的是正面望鏡頭、沒有人頭遮擋，加上光線充足。同一個人、同一套向量，分數就從
              0.267 升到了 0.456。
            </p>
            <p>
              其餘十格裡面，Karen（0.411）、Carina（0.406）、暐翹（0.380）和咖喱（0.363）都只差一點，一共{' '}
              <span className={NUM}>{POSED_FRAME.recognitionCount}</span> 位認定、
              <span className={NUM}>
                {POSED_FRAME.candidateCount - POSED_FRAME.recognitionCount}
              </span>{' '}
              位候選、
              <span className={NUM}>
                {POSED_FRAME.faces.length - POSED_FRAME.candidateCount}
              </span>{' '}
              位未過檻。有意思的是排位，左邊數起這十一格的最佳候選（Karen、暐翹、何佩、咖喱、Ada、Carina、莎莎……到最右邊的蘇菲），順序剛好跟網民逐個認出來的次序對得上。
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <h2 className="font-kai text-[18px] leading-tight text-carbon-deep">
            同一班人，一段 23 秒的片
          </h2>

          <div className="flex max-w-[76ch] flex-col gap-1 border-l-2 border-carbon-deep/20 pl-3">
            <a
              href={VIDEO_POST.url}
              target="_blank"
              rel="noreferrer noopener"
              className="font-mono text-[12px] text-carbon-soft underline decoration-carbon-deep/20 underline-offset-2 hover:decoration-carbon-deep"
            >
              Instagram Reel · @{VIDEO_POST.handle}
            </a>
            <span className="whitespace-pre-line font-kai text-[14px] leading-relaxed text-carbon">
              {VIDEO_POST.caption}
            </span>
          </div>

          <p className="max-w-[76ch] font-kai text-[14px] leading-relaxed text-carbon">
            當晚在現場拍好的 23 秒短片後來也找到了。交給同一套管線跑（每秒取 6 格、det_size
            640、門檻 {SITE_THRESHOLD.toFixed(3)}），共抽了{' '}
            <span className={NUM}>{VIDEO_REPORT.frames}</span> 個影格、偵測到{' '}
            <span className={NUM}>{VIDEO_REPORT.detections}</span> 張臉，其中{' '}
            <span className={NUM}>{VIDEO_REPORT.recognitions}</span> 次過檻，認出{' '}
            <span className={NUM}>{VIDEO_REPORT.contestants}</span> 位參賽者。
          </p>

          <Card padding="none" className="max-w-[640px] overflow-x-auto">
            <table className="w-full border-collapse">
              <caption className="px-3 py-2 text-left font-kai text-[13px] text-carbon-soft">
                影片逐位統計 · 過檻次數與最高餘弦
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
                    帳號
                  </th>
                  <th scope="col" className={CELL}>
                    過檻次數
                  </th>
                  <th scope="col" className={CELL}>
                    最高
                  </th>
                  <th scope="col" className={CELL}>
                    中位
                  </th>
                </tr>
              </thead>
              <tbody>
                {VIDEO_REPORT.rows.map((row) => (
                  <tr key={row.id} className="hover:bg-tint">
                    <td className={`${CELL} ${NUM} text-carbon-soft`}>{row.id}</td>
                    <td className={`${CELL} font-kai text-[13px] text-carbon-deep`}>
                      {row.nickname}
                    </td>
                    <td className={`${CELL} font-mono text-[12px] text-ink-muted`}>
                      {(() => {
                        if (row.id === '15') return `@${VIDEO_POST.handle}`;
                        const handle = VIDEO_HANDLES.find((entry) => entry.id === row.id);
                        return handle ? `@${handle.handle}` : '—';
                      })()}
                    </td>
                    <td className={`${CELL} ${NUM} text-carbon-soft`}>{row.count}</td>
                    <td className={`${CELL} ${NUM} text-carbon`}>{row.best.toFixed(3)}</td>
                    <td className={`${CELL} ${NUM} text-ink-muted`}>{row.median.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          <div className="flex max-w-[76ch] flex-col gap-3 font-kai text-[14px] leading-relaxed text-carbon">
            <p>
              靜態相片跑了幾張才認出一位，換成這段 23 秒的片，十一位每人都有 21 至 56
              個影格過線，最高去到{' '}
              <span className={NUM}>
                {Math.max(...VIDEO_REPORT.rows.map((r) => r.best)).toFixed(3)}
              </span>
              。影片裡的臉跟相片一樣細，但每個人在鏡頭前出現了幾十次，有幾格總會影得正面又清楚。
            </p>
            <p>
              帖文裡 @carinalxt 標註了十個帳號，連同她自己正好十一人。逐個對過各自的 IG
              簡介，就跟上表認出來的十一位完全吻合，包括之前認不齊的超酸（79 號）、阿杰（31
              號）和馬欣（78 號）。
            </p>
            <p>這條 6.3 MB 的片沒有複製到本站伺服器，想看原片直接點上面的 Instagram 連結就可以。</p>
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <h2 className="font-kai text-[18px] leading-tight text-carbon-deep">帖文下的回覆</h2>

          <p className="max-w-[76ch] font-kai text-[14px] leading-relaxed text-carbon">
            @zisha_1001 的原帖有 63 個回覆，未登入只能看到最前面五個。網民猜的團大致有三類：造星
            IV、VIVA 和 Cookies。VIVA 的 {VIVA_COVERAGE.members} 位成員裡有 {VIVA_COVERAGE.inRoster}{' '}
            位（Carina 15 號、Ada 27 號）本身就是造星 IV 出來，所以前面兩個講法其實指同一班人；至於
            VIVA 另外兩位馬思惠和張鈊貽不在這 {CONTESTANT_COUNT}{' '}
            人名冊內，本站本來就沒有她們的向量。
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
            另外也有看過帖文的讀者提醒，樓下還有{' '}
            {REPORTED_REPLY_AUTHORS.map((c) => `${c.name}（${c.nickname}，${c.id} 號）`).join('、')}{' '}
            留言。未登入刷不到那條回覆，所以這裡只記錄這件事，不引述原話。連同親自留了言的莎莎，已經有兩位當事人在帖文出現。
          </p>
        </div>

        <div className="flex flex-col gap-4">
          <h2 className="font-kai text-[18px] leading-tight text-carbon-deep">人手 vs 機器</h2>

          <p className="max-w-[76ch] font-kai text-[14px] leading-relaxed text-carbon">
            拿觀眾靠眼認出來的九位去對過馬路和排隊那兩張 1085 px
            街拍。「最高餘弦」是該位參賽者在全部 {TOTALS.faces} 個框裡拿到的最高分，「排名」是她在{' '}
            {CONTESTANT_COUNT} 位參賽者中的名次，「高於雜訊」則看有沒有跨過其餘{' '}
            {CONTESTANT_COUNT - 9} 位的第 90 百分位（
            <span className="font-mono tabular-nums">{ROSTER_NOISE.p90.toFixed(3)}</span>）。
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
                    <td className={`${CELL} ${NUM} text-carbon-soft`}>
                      {c.rank}/{CONTESTANT_COUNT}
                    </td>
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
              九位裡面跨過雜訊線的只有 {clearsNoise.length} 位（
              {clearsNoise.map((c, index) => (
                <span key={c.id}>
                  {index > 0 ? '、' : ''}
                  {c.nickname} <span className={NUM}>{c.best.toFixed(3)}</span>（第 {c.rank}）
                </span>
              ))}
              ），另外 {belowNoise.length} 位落在{' '}
              <span className={NUM}>{Math.min(...belowNoise.map((c) => c.best)).toFixed(3)}</span>–
              <span className={NUM}>{Math.max(...belowNoise.map((c) => c.best)).toFixed(3)}</span>{' '}
              之間，跟名單以外 {CONTESTANT_COUNT - named.length} 位的平均分（
              <span className={NUM}>{ROSTER_NOISE.mean.toFixed(3)}</span>
              ）混在一起。至於被猜「好似見到」的 Ivy So，她在街拍最高只有{' '}
              <span className={NUM}>{ivy.best.toFixed(3)}</span>、排第 {ivy.rank}
              ，和上面的原片名單對起來也確實沒見到她。
            </p>
            <p>
              最明顯的落差在莎莎與蘇菲身上。兩個人在原片裡分別過了 32 次和 53 次門檻，也都有在
              Threads 帖文下出現，但在那兩張 1085 px 街拍裡卻只拿到{' '}
              <span className={NUM}>{sasa.best.toFixed(3)}</span> 和{' '}
              <span className={NUM}>{sophie.best.toFixed(3)}</span>，低過雜訊線{' '}
              <span className={NUM}>{ROSTER_NOISE.p90.toFixed(3)}</span>
              。單憑一兩張模糊街拍的低分，真的說明不了什麼。
            </p>
            <p>
              看過節目的人認得出，靠的是髮型、身形和同行的人；ArcFace
              只能看臉框裡那幾十個像素。如果把名單全部拿掉，讓管線直接在 {CONTESTANT_COUNT}{' '}
              位裡亂挑，{OPEN_TOP1.boxes} 個框的最高分會散到{' '}
              <span className="font-mono text-[13px]">{OPEN_TOP1.distinct}</span> 位不同人身上（像
              {OPEN_TOP1.repeated.map((r, i) => (
                <span key={r.nickname}>
                  {i > 0 ? '、' : ''}
                  {r.nickname}
                  {r.times > 2 ? ` ×${r.times}` : ''}
                </span>
              ))}
              ）。十一個人左右的隊不會認出十幾個人，這些單張圖的最高分就先留白，不把名字印出來。
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-4">
          <h2 className="font-kai text-[18px] leading-tight text-carbon-deep">
            同一張相、三個解像度
          </h2>

          <p className="max-w-[76ch] font-kai text-[14px] leading-relaxed text-carbon">
            後來在網上又找到同一格過馬路畫面的另外兩個版本，拼成三個解像度：聊天轉貼的 1085 px
            截圖、@rinrinrin1666 轉貼的 1600 px 版，還有原帖的 4032 px 原檔。臉由{' '}
            {RESOLUTION_LADDER.frames[0].facePx} 變成 {RESOLUTION_LADDER.frames[2].facePx}{' '}
            像素，三個版本各自偵測並重跑：
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
              兩個原本就認得到的錨點（
              {RESOLUTION_LADDER.rows
                .filter((row) => Math.max(...row.scores) - Math.min(...row.scores) <= 0.02)
                .map((row) => row.nickname)
                .join('、')}
              ）在三個版本之間的擺幅不超過
              0.02。臉的像素放大了十幾倍，餘弦幾乎沒動過，可見分數低主要卡在光線、角度跟參考照的差距。
            </p>
            <p>
              何佩和咖喱的擺幅稍微大一點，但沒有跟解像度一起往上升，像何佩在 4032 px 原檔反而從
              0.294 跌回
              0.228。每張圖偵測到的臉框位置切法略有不同，框偏一點帶來的分數波動，比換高畫質原圖還大。
            </p>
            <p>
              三個版本各自抓到的臉數也不完全一樣（
              {RESOLUTION_LADDER.frames
                .map((frame) => `${frame.label}有 ${frame.faces} 張`)
                .join('、')}
              ，1600 px 版因為邊緣多裁進一個人而多出一個框）。
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
              把 {REFERENCE_COUNT}{' '}
              個參考向量拿去兩兩比對「其他參賽者」，就能看到把門檻往下調會換來多少誤認：
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
                    {passes(loosen.cutoff) - TOTALS.accepted} 個名字，代價是參考庫裡{' '}
                    <span className={NUM}>{(loosen.rate * 100).toFixed(0)}%</span>{' '}
                    的向量都會錯配成別人。就算退到本頁用的{' '}
                    <span className={NUM}>{JOB_THRESHOLD.toFixed(2)}</span>，錯配率依然有約{' '}
                    <span className={NUM}>{(jobRate * 100).toFixed(0)}%</span>
                    ，只適合拿來找線索。
                  </>
                );
              })()}
            </p>
            <p>
              至於 Sogo 門外排隊那張為什麼原生解像度一個框都抓不到，是因為裡面的人臉只有 14×19
              像素，低於偵測器設定的{' '}
              <span className="font-mono text-[13px]">min_face_size: 20</span>
              。把那一帶放大四倍切成小格重掃之後，才終於抓回十個框。
            </p>
            <p>
              為了量出縮圖對分數的影響，我們把過馬路那張裡 9
              張較清楚的臉逐級縮細再重新抽向量，跟原生向量比對餘弦：
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
              縮到街拍常見的 18 至 20 像素高時，同一張臉自己對自己就會跌剩大約{' '}
              <span className="font-mono text-[13px]">0.79</span>
              。本來參考庫裡同一個人的兩張相平均分數是 {MATCHER_CHECK.genuineMean.toFixed(3)}（
              {(MATCHER_CHECK.genuineAboveThreshold * 100).toFixed(0)}% 過{' '}
              {SITE_THRESHOLD.toFixed(3)}），陌生人最高可以去到{' '}
              {MATCHER_CHECK.impostorMax.toFixed(3)}
              。兩邊原本就靠得很近，遇上側臉、遮擋再加上低像素，就容易掉出門檻外。這也是為什麼前面那張正面合照哪怕只有
              32×41 像素也能認出何佩，而 4032 px 的模糊側臉還是過不了線。
            </p>
            <p>
              其餘沒過線的框，第一位與第二位的分數差距只有{' '}
              <span className="font-mono text-[13px]">{TOTALS.tightestMargin.toFixed(3)}</span> 到{' '}
              <span className="font-mono text-[13px]">{TOTALS.widestMargin.toFixed(3)}</span>
              ，分不出誰更像誰，表格裡就只留數字。
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
            相片版權屬拍攝者。兩張街拍取自{' '}
            <a
              href="https://www.threads.com/@zisha_1001/post/DfuWFhMH-4X"
              target="_blank"
              rel="noreferrer noopener"
              className="underline decoration-carbon-deep/30 underline-offset-2 hover:decoration-carbon-deep"
            >
              Threads · @zisha_1001
            </a>
            ，1600 px 轉貼取自{' '}
            <a
              href="https://www.threads.com/@rinrinrin1666/post/DfzERn0k9HS"
              target="_blank"
              rel="noreferrer noopener"
              className="underline decoration-carbon-deep/30 underline-offset-2 hover:decoration-carbon-deep"
            >
              @rinrinrin1666（轉貼）
            </a>
            ，正面合照取自{' '}
            <a
              href="https://www.threads.com/@rinrinrin1666/post/DgH5FprE51B"
              target="_blank"
              rel="noreferrer noopener"
              className="underline decoration-carbon-deep/30 underline-offset-2 hover:decoration-carbon-deep"
            >
              @rinrinrin1666（合照）
            </a>
            ，23 秒短片連結自{' '}
            <a
              href={VIDEO_POST.url}
              target="_blank"
              rel="noreferrer noopener"
              className="underline decoration-carbon-deep/30 underline-offset-2 hover:decoration-carbon-deep"
            >
              @carinalxt
            </a>
            （均非《全民造星
            IV》官方素材）。本站只為核對辨識結果而複製靜態相片，沒有其他用途；拍攝者或相中人如要移除，在原帖回覆一句即可，本頁會連相一併下架。框的位置以幀比例存，乘以顯示尺寸即為像素位置。
          </span>
        </div>
      </div>
    </div>
  );
}
