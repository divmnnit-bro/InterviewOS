import { WindowTime } from '@/types/api';

/**
 * Sorts windows chronologically and merges any that overlap or touch.
 */
export function mergeOverlappingWindows(windows: WindowTime[]): WindowTime[] {
  if (windows.length <= 1) return [...windows];

  // Parse and sort by start time
  const sorted = [...windows].sort(
    (a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime()
  );

  const merged: WindowTime[] = [];
  let current = sorted[0];

  for (let i = 1; i < sorted.length; i++) {
    const next = sorted[i];
    const currentEnd = new Date(current.end_time).getTime();
    const nextStart = new Date(next.start_time).getTime();
    const nextEnd = new Date(next.end_time).getTime();

    // If next starts before or exactly when current ends (touching or overlapping)
    if (nextStart <= currentEnd) {
      // Merge by expanding current window's end time if next ends later
      if (nextEnd > currentEnd) {
        current = {
          start_time: current.start_time,
          end_time: next.end_time,
        };
      }
    } else {
      merged.push(current);
      current = next;
    }
  }

  merged.push(current);
  return merged;
}

/**
 * Clips availability windows to the boundaries of a drive window [driveStart, driveEnd].
 * Windows completely outside are discarded.
 */
export function clipToDriveWindow(
  windows: WindowTime[],
  driveStart: string,
  driveEnd: string
): WindowTime[] {
  const dStart = new Date(driveStart).getTime();
  const dEnd = new Date(driveEnd).getTime();

  const clipped: WindowTime[] = [];

  for (const w of windows) {
    const wStart = new Date(w.start_time).getTime();
    const wEnd = new Date(w.end_time).getTime();

    // Completely outside
    if (wEnd <= dStart || wStart >= dEnd) {
      continue;
    }

    const effectiveStart = new Date(Math.max(wStart, dStart)).toISOString().replace('.000Z', 'Z');
    const effectiveEnd = new Date(Math.min(wEnd, dEnd)).toISOString().replace('.000Z', 'Z');

    clipped.push({
      start_time: effectiveStart,
      end_time: effectiveEnd,
    });
  }

  return mergeOverlappingWindows(clipped);
}

/**
 * Validates that start_time is strictly before end_time.
 */
export function isValidWindow(start: string, end: string): boolean {
  const s = new Date(start).getTime();
  const e = new Date(end).getTime();
  return !isNaN(s) && !isNaN(e) && s < e;
}
