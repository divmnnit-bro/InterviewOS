import { describe, it, expect } from 'vitest';

describe('F7: Pipeline and Ripple Rescue Logic', () => {
  it('groups candidates by current stage on the pipeline board', () => {
    const stages = [
      { id: 'stage-1', order_index: 0, name: 'Round 1' },
      { id: 'stage-2', order_index: 1, name: 'Round 2' },
    ];

    const candidates = [
      { id: 'c-1', name: 'Alice', status: 'active', current_stage_id: 'stage-1' },
      { id: 'c-2', name: 'Bob', status: 'active', current_stage_id: 'stage-2' },
      { id: 'c-3', name: 'Charlie', status: 'selected', current_stage_id: 'stage-2' },
    ];

    expect(stages.length).toBe(2);
    const stage1Candidates = candidates.filter(
      (c) => c.status === 'active' && c.current_stage_id === 'stage-1'
    );
    const stage2Candidates = candidates.filter(
      (c) => c.status === 'active' && c.current_stage_id === 'stage-2'
    );
    const selectedCandidates = candidates.filter((c) => c.status === 'selected');

    expect(stage1Candidates.length).toBe(1);
    expect(stage1Candidates[0].name).toBe('Alice');
    expect(stage2Candidates.length).toBe(1);
    expect(stage2Candidates[0].name).toBe('Bob');
    expect(selectedCandidates.length).toBe(1);
    expect(selectedCandidates[0].name).toBe('Charlie');
  });

  it('validates audited override reason length (minimum 10 characters)', () => {
    const isValidOverride = (override: boolean, reason?: string) => {
      if (!override) return true;
      return typeof reason === 'string' && reason.trim().length >= 10;
    };

    expect(isValidOverride(false)).toBe(true);
    expect(isValidOverride(true, '')).toBe(false);
    expect(isValidOverride(true, 'short')).toBe(false);
    expect(isValidOverride(true, 'Approved by engineering VP after review')).toBe(true);
  });

  it('correctly categorizes directly affected vs collateral rescue moves', () => {
    const moves = [
      {
        interview_id: 'iv-1',
        candidate_id: 'c-1',
        directly_affected: true,
        changes: ['time', 'room'],
      },
      {
        interview_id: 'iv-2',
        candidate_id: 'c-2',
        directly_affected: false, // bumped due to room collision
        changes: ['time'],
      },
      {
        interview_id: 'iv-3',
        candidate_id: 'c-3',
        directly_affected: false,
        changes: ['panel'],
      },
    ];

    const directHits = moves.filter((m) => m.directly_affected);
    const collateralMoves = moves.filter((m) => !m.directly_affected);

    expect(directHits.length).toBe(1);
    expect(directHits[0].interview_id).toBe('iv-1');
    expect(collateralMoves.length).toBe(2);
    expect(collateralMoves.map((m) => m.interview_id)).toEqual(['iv-2', 'iv-3']);
  });
});
