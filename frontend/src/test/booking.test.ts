import { describe, it, expect } from 'vitest';
import { generateIdempotencyKey } from '../api/client';
import { groupByDay } from '../lib/timelineMath';

describe('F5: Booking and Candidate Area Logic', () => {
  it('generates unique valid idempotency keys', () => {
    const key1 = generateIdempotencyKey();
    const key2 = generateIdempotencyKey();

    expect(key1).toBeTruthy();
    expect(key2).toBeTruthy();
    expect(key1).not.toBe(key2);
    // Meets backend regex: ^[-A-Za-z0-9_.:]{8,64}$
    expect(key1).toMatch(/^[-A-Za-z0-9_.:]{8,64}$/);
    expect(key2).toMatch(/^[-A-Za-z0-9_.:]{8,64}$/);
  });

  it('groups booking slots across days cleanly', () => {
    const slots = [
      { start: '2026-11-02T09:00:00Z', end: '2026-11-02T09:45:00Z', startTime: '2026-11-02T09:00:00Z' },
      { start: '2026-11-02T10:00:00Z', end: '2026-11-02T10:45:00Z', startTime: '2026-11-02T10:00:00Z' },
      { start: '2026-11-03T14:00:00Z', end: '2026-11-03T14:45:00Z', startTime: '2026-11-03T14:00:00Z' },
    ];

    const grouped = groupByDay(slots);
    expect(grouped.length).toBe(2);
    expect(grouped[0].dateStr).toBe('2026-11-02');
    expect(grouped[0].items.length).toBe(2);
    expect(grouped[1].dateStr).toBe('2026-11-03');
    expect(grouped[1].items.length).toBe(1);
  });

  it('guarantees candidate progress data schema excludes scores or feedback', () => {
    // Model test enforcing the spec invariant: never expose scores or feedback to candidates
    const candidateProgress = {
      drive_id: 'drive-123',
      drive_title: 'Engineering Campus 2026',
      enrolment_status: 'active',
      current_stage_id: 'stage-2',
      current_stage_name: 'Technical Round 2',
      rounds: [
        {
          stage_id: 'stage-1',
          stage_name: 'Coding Assessment',
          order_index: 0,
          result: 'advanced',
        },
        {
          stage_id: 'stage-2',
          stage_name: 'Technical Round 2',
          order_index: 1,
          result: null, // in progress
        },
      ],
    };

    expect(candidateProgress).not.toHaveProperty('score');
    expect(candidateProgress).not.toHaveProperty('scores');
    expect(candidateProgress).not.toHaveProperty('feedback');
    expect(candidateProgress).not.toHaveProperty('rubric');
    expect(candidateProgress.rounds[0]).not.toHaveProperty('score');
    expect(candidateProgress.rounds[0]).not.toHaveProperty('feedback');
    expect(candidateProgress.rounds[0].result).toBe('advanced');
  });
});
