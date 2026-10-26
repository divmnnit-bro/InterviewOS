/**
 * Mathematics and layout utilities for Schedule Timeline (Room & Interviewer views).
 */

export interface TimelineSlot {
  id: string;
  title: string;
  candidateName: string;
  stageName: string;
  roomName?: string;
  panelNames: string[];
  startTime: string; // ISO string
  endTime: string;   // ISO string
  status: string;
  isProposal?: boolean;
}

export interface DayGroup<T> {
  dateStr: string; // YYYY-MM-DD
  label: string;   // e.g. "Mon, Nov 2"
  items: T[];
}

export interface InterviewerDayLoad {
  interviewerId: string;
  interviewerName: string;
  dateStr: string;
  count: number;
  capacity: number;
  isOverCapacity: boolean;
  isAtCapacity: boolean;
}

/**
 * Parses date string YYYY-MM-DD from an ISO string in local or given reference.
 */
export function getDateString(isoStr: string): string {
  const d = new Date(isoStr);
  const year = d.getUTCFullYear();
  const month = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Formats a time string (HH:MM) in UTC for consistent timeline positioning.
 */
export function formatTimeUTC(isoStr: string): string {
  const d = new Date(isoStr);
  const hours = String(d.getUTCHours()).padStart(2, '0');
  const minutes = String(d.getUTCMinutes()).padStart(2, '0');
  return `${hours}:${minutes}`;
}

/**
 * Computes minutes from midnight UTC.
 */
export function getMinutesFromMidnightUTC(isoStr: string): number {
  const d = new Date(isoStr);
  return d.getUTCHours() * 60 + d.getUTCMinutes();
}

/**
 * Calculates percentage offset and width for a slot given a day's start and end hours (e.g. 8 to 18).
 */
export function calculateSlotPosition(
  startTimeIso: string,
  endTimeIso: string,
  dayStartHour: number = 8,
  dayEndHour: number = 18
): { leftPercent: number; widthPercent: number } {
  const totalDayMinutes = (dayEndHour - dayStartHour) * 60;
  if (totalDayMinutes <= 0) return { leftPercent: 0, widthPercent: 100 };

  const startMinutes = getMinutesFromMidnightUTC(startTimeIso) - dayStartHour * 60;
  const endMinutes = getMinutesFromMidnightUTC(endTimeIso) - dayStartHour * 60;

  const boundedStart = Math.max(0, Math.min(totalDayMinutes, startMinutes));
  const boundedEnd = Math.max(boundedStart, Math.min(totalDayMinutes, endMinutes));

  const leftPercent = (boundedStart / totalDayMinutes) * 100;
  const widthPercent = Math.max(1, ((boundedEnd - boundedStart) / totalDayMinutes) * 100);

  return { leftPercent, widthPercent };
}

/**
 * Groups items by day (YYYY-MM-DD).
 */
export function groupByDay<T extends { startTime: string }>(items: T[]): DayGroup<T>[] {
  const groups = new Map<string, T[]>();

  for (const item of items) {
    const day = getDateString(item.startTime);
    if (!groups.has(day)) {
      groups.set(day, []);
    }
    groups.get(day)!.push(item);
  }

  const result: DayGroup<T>[] = [];
  const sortedKeys = Array.from(groups.keys()).sort();

  for (const key of sortedKeys) {
    const dateObj = new Date(key + 'T00:00:00Z');
    const label = dateObj.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      timeZone: 'UTC',
    });
    result.push({
      dateStr: key,
      label,
      items: groups.get(key)!,
    });
  }

  return result;
}

/**
 * Calculates interview load per interviewer for a specific day.
 */
export function calculateInterviewerLoads(
  interviews: Array<{ startTime: string; interviewerIds: string[] }>,
  interviewers: Array<{ id: string; name: string; capacity?: number }>,
  dateStr: string
): InterviewerDayLoad[] {
  const dayInterviews = interviews.filter((i) => getDateString(i.startTime) === dateStr);
  const countMap = new Map<string, number>();

  for (const iv of dayInterviews) {
    for (const iid of iv.interviewerIds) {
      countMap.set(iid, (countMap.get(iid) || 0) + 1);
    }
  }

  return interviewers.map((inv) => {
    const count = countMap.get(inv.id) || 0;
    const capacity = inv.capacity && inv.capacity > 0 ? inv.capacity : 4;
    return {
      interviewerId: inv.id,
      interviewerName: inv.name,
      dateStr,
      count,
      capacity,
      isOverCapacity: count > capacity,
      isAtCapacity: count === capacity,
    };
  });
}
