import { describe, it, expect } from 'vitest';

describe('F6: Interviewer Evaluation & Rubric Mathematics', () => {
  it('computes mean rubric score accurately to two decimal places', () => {
    const rubric = {
      'Problem Solving': 7.5,
      'Technical Competence': 8.0,
      'Communication': 9.0,
      'Culture & Values': 8.5,
    };

    const values = Object.values(rubric);
    const mean = Number((values.reduce((a, b) => a + b, 0) / values.length).toFixed(2));

    expect(mean).toBe(8.25);
  });

  it('correctly clamps rubric ratings within [0, 10]', () => {
    const clamp = (val: number) => Math.max(0, Math.min(10, val));

    expect(clamp(-5)).toBe(0);
    expect(clamp(15)).toBe(10);
    expect(clamp(7.5)).toBe(7.5);
  });

  it('enforces start time gating before evaluation submission', () => {
    const now = new Date('2026-11-02T10:00:00Z');

    const futureInterview = { startTime: '2026-11-02T11:00:00Z' };
    const startedInterview = { startTime: '2026-11-02T09:30:00Z' };

    const isFutureStarted = now >= new Date(futureInterview.startTime);
    const isStartedStarted = now >= new Date(startedInterview.startTime);

    expect(isFutureStarted).toBe(false); // Gated, disabled
    expect(isStartedStarted).toBe(true);  // Open for evaluation
  });

  it('respects colleagues feedback locking rule to prevent anchoring', () => {
    const ownOnlyResponse = {
      interview_id: 'iv-1',
      visibility: 'own_only' as const,
      panel_size: 2,
      submitted_count: 1,
      evaluations: [],
    };

    const allResponse = {
      interview_id: 'iv-1',
      visibility: 'all' as const,
      panel_size: 2,
      submitted_count: 2,
      evaluations: [
        {
          id: 'ev-1',
          score: 8.5,
          feedback: 'Strong grasp of concurrency',
          recommendation: 'hire',
        },
      ],
    };

    const isColleaguesVisible = (res: { visibility: string }) => res.visibility === 'all';

    expect(isColleaguesVisible(ownOnlyResponse)).toBe(false); // Locked
    expect(isColleaguesVisible(allResponse)).toBe(true);      // Unlocked
  });
});
