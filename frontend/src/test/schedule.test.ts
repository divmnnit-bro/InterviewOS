import { describe, it, expect } from 'vitest';
import {
  calculateSlotPosition,
  getDateString,
  getMinutesFromMidnightUTC,
  groupByDay,
  calculateInterviewerLoads,
} from '../lib/timelineMath';

describe('timelineMath', () => {
  it('extracts date string correctly', () => {
    expect(getDateString('2026-11-02T09:30:00Z')).toBe('2026-11-02');
    expect(getDateString('2026-12-31T23:59:59Z')).toBe('2026-12-31');
  });

  it('calculates minutes from midnight UTC correctly', () => {
    expect(getMinutesFromMidnightUTC('2026-11-02T00:00:00Z')).toBe(0);
    expect(getMinutesFromMidnightUTC('2026-11-02T09:30:00Z')).toBe(9 * 60 + 30);
    expect(getMinutesFromMidnightUTC('2026-11-02T18:00:00Z')).toBe(18 * 60);
  });

  it('calculates slot position percentage accurately across day hours', () => {
    // Day starts at 08:00 (480 mins) and ends at 18:00 (1080 mins), total 600 mins.
    // Slot: 09:00 (540 mins) to 10:00 (600 mins).
    // Start offset = 60 mins -> (60 / 600) * 100 = 10%
    // Duration = 60 mins -> (60 / 600) * 100 = 10%
    const pos = calculateSlotPosition(
      '2026-11-02T09:00:00Z',
      '2026-11-02T10:00:00Z',
      8,
      18
    );
    expect(pos.leftPercent).toBeCloseTo(10, 2);
    expect(pos.widthPercent).toBeCloseTo(10, 2);
  });

  it('clips positions gracefully when slot is outside day boundaries', () => {
    // Slot starts before day start (07:00 vs 08:00)
    const pos = calculateSlotPosition(
      '2026-11-02T07:00:00Z',
      '2026-11-02T09:00:00Z',
      8,
      18
    );
    expect(pos.leftPercent).toBe(0);
    // Only 08:00 to 09:00 is visible (60 mins out of 600 mins = 10%)
    expect(pos.widthPercent).toBeCloseTo(10, 2);
  });

  it('groups interviews by day', () => {
    const items = [
      { id: '1', startTime: '2026-11-02T09:00:00Z' },
      { id: '2', startTime: '2026-11-02T11:00:00Z' },
      { id: '3', startTime: '2026-11-03T10:00:00Z' },
    ];
    const grouped = groupByDay(items);
    expect(grouped.length).toBe(2);
    expect(grouped[0].dateStr).toBe('2026-11-02');
    expect(grouped[0].items.length).toBe(2);
    expect(grouped[1].dateStr).toBe('2026-11-03');
    expect(grouped[1].items.length).toBe(1);
  });

  it('calculates interviewer daily loads and compares with capacity', () => {
    const interviewers = [
      { id: 'inv-1', name: 'Alice Smith', capacity: 3 },
      { id: 'inv-2', name: 'Bob Jones', capacity: 2 },
    ];

    const interviews = [
      { startTime: '2026-11-02T09:00:00Z', interviewerIds: ['inv-1', 'inv-2'] },
      { startTime: '2026-11-02T10:00:00Z', interviewerIds: ['inv-1', 'inv-2'] },
      { startTime: '2026-11-02T11:00:00Z', interviewerIds: ['inv-1'] },
      { startTime: '2026-11-02T14:00:00Z', interviewerIds: ['inv-1'] }, // inv-1 has 4 (capacity 3 -> over capacity!)
    ];

    const loads = calculateInterviewerLoads(interviews, interviewers, '2026-11-02');
    const aliceLoad = loads.find((l) => l.interviewerId === 'inv-1')!;
    const bobLoad = loads.find((l) => l.interviewerId === 'inv-2')!;

    expect(aliceLoad.count).toBe(4);
    expect(aliceLoad.capacity).toBe(3);
    expect(aliceLoad.isOverCapacity).toBe(true);

    expect(bobLoad.count).toBe(2);
    expect(bobLoad.capacity).toBe(2);
    expect(bobLoad.isAtCapacity).toBe(true);
    expect(bobLoad.isOverCapacity).toBe(false);
  });
});
