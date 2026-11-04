const two = (n: number) => String(n).padStart(2, '0');

/** A slip's timestamp, `MM-DD HH:mm` local. An unparseable string is shown as it came. */
export function slipTime(value: string | Date): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return `${two(date.getMonth() + 1)}-${two(date.getDate())} ${two(date.getHours())}:${two(date.getMinutes())}`;
}

/**
 * Where the open track sits in the current view. The sheet is docked, so filters stay usable
 * while it's open and can take the open track out of view (`index` -1).
 */
export function sheetPosition(index: number, total: number): string {
  return index < 0 ? '不在目前篩選內' : `在列第 ${index + 1} / ${total} 張`;
}
