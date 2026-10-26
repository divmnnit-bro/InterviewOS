import { describe, it, expect } from 'vitest';
import {
  mergeOverlappingWindows,
  clipToDriveWindow,
  isValidWindow,
} from '../lib/availabilityMath';
import { WindowTime } from '../types/api';

describe('F3: Availability Window Maths', () => {
  it('validates window start and end times', () => {
    expect(isValidWindow('2026-11-02T09:00:00Z', '2026-11-02T17:00:00Z')).toBe(true);
    expect(isValidWindow('2026-11-02T17:00:00Z', '2026-11-02T09:00:00Z')).toBe(false);
    expect(isValidWindow('2026-11-02T09:00:00Z', '2026-11-02T09:00:00Z')).toBe(false);
    expect(isValidWindow('invalid', 'date')).toBe(false);
  });

  it('merges overlapping windows into a single continuous window', () => {
    const input: WindowTime[] = [
      { start_time: '2026-11-02T09:00:00Z', end_time: '2026-11-02T12:00:00Z' },
      { start_time: '2026-11-02T11:00:00Z', end_time: '2026-11-02T14:00:00Z' },
    ];

    const merged = mergeOverlappingWindows(input);
    expect(merged).toHaveLength(1);
    expect(merged[0]).toEqual({
      start_time: '2026-11-02T09:00:00Z',
      end_time: '2026-11-02T14:00:00Z',
    });
  });

  it('merges touching windows', () => {
    const input: WindowTime[] = [
      { start_time: '2026-11-02T09:00:00Z', end_time: '2026-11-02T12:00:00Z' },
      { start_time: '2026-11-02T12:00:00Z', end_time: '2026-11-02T17:00:00Z' },
    ];

    const merged = mergeOverlappingWindows(input);
    expect(merged).toHaveLength(1);
    expect(merged[0]).toEqual({
      start_time: '2026-11-02T09:00:00Z',
      end_time: '2026-11-02T17:00:00Z',
    });
  });

  it('preserves disjoint non-overlapping windows', () => {
    const input: WindowTime[] = [
      { start_time: '2026-11-02T09:00:00Z', end_time: '2026-11-02T11:00:00Z' },
      { start_time: '2026-11-02T14:00:00Z', end_time: '2026-11-02T17:00:00Z' },
    ];

    const merged = mergeOverlappingWindows(input);
    expect(merged).toHaveLength(2);
    expect(merged[0].end_time).toBe('2026-11-02T11:00:00Z');
    expect(merged[1].start_time).toBe('2026-11-02T14:00:00Z');
  });

  it('clips windows extending beyond drive boundaries', () => {
    const driveStart = '2026-11-02T10:00:00Z';
    const driveEnd = '2026-11-02T16:00:00Z';

    const input: WindowTime[] = [
      // Starts before drive
      { start_time: '2026-11-02T08:00:00Z', end_time: '2026-11-02T12:00:00Z' },
      // Ends after drive
      { start_time: '2026-11-02T14:00:00Z', end_time: '2026-11-02T18:00:00Z' },
      // Completely outside before
      { start_time: '2026-11-02T06:00:00Z', end_time: '2026-11-02T08:00:00Z' },
      // Completely outside after
      { start_time: '2026-11-02T18:00:00Z', end_time: '2026-11-02T20:00:00Z' },
    ];

    const clipped = clipToDriveWindow(input, driveStart, driveEnd);
    expect(clipped).toHaveLength(2);
    expect(clipped[0]).toEqual({
      start_time: '2026-11-02T10:00:00Z',
      end_time: '2026-11-02T12:00:00Z',
    });
    expect(clipped[1]).toEqual({
      start_time: '2026-11-02T14:00:00Z',
      end_time: '2026-11-02T16:00:00Z',
    });
  });

  it('handles multiple overlapping and enclosed windows in arbitrary order', () => {
    const input: WindowTime[] = [
      { start_time: '2026-11-02T13:00:00Z', end_time: '2026-11-02T15:00:00Z' },
      { start_time: '2026-11-02T09:00:00Z', end_time: '2026-11-02T17:00:00Z' }, // encloses previous
      { start_time: '2026-11-02T10:00:00Z', end_time: '2026-11-02T12:00:00Z' }, // encloses
    ];

    const merged = mergeOverlappingWindows(input);
    expect(merged).toHaveLength(1);
    expect(merged[0]).toEqual({
      start_time: '2026-11-02T09:00:00Z',
      end_time: '2026-11-02T17:00:00Z',
    });
  });
});
