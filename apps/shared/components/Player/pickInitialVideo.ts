/**
 * Choose which video the Player opens with.
 *
 * `initialVideoId` comes from the `?video=` query param, which `URLSearchParams.get`
 * has already percent-decoded — so it compares directly against `Video.id`, even
 * though every MV id contains CJK, spaces and 《》 and is encoded in the link.
 *
 * Falls back to the first video, which is what the Player did unconditionally before
 * — and why 4 of the 5 published MVs were unreachable from the home page.
 */
export function pickInitialVideo<T extends { id: string }>(
  videos: T[],
  initialVideoId: string | null,
): T | undefined {
  return videos.find((v) => v.id === initialVideoId) ?? videos[0];
}
