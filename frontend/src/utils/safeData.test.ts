import { describe, expect, it } from 'vitest';
import { toDisplayStringRecord } from './safeData';

describe('toDisplayStringRecord', () => {
  it('keeps displayable primitives and drops unsafe nested values', () => {
    expect(toDisplayStringRecord({
      nationality: 'British',
      age: 42,
      confirmed: true,
      passport: { number: 'secret' },
      aliases: ['one', 'two'],
      invalidNumber: Number.POSITIVE_INFINITY,
    })).toEqual({ nationality: 'British', age: '42', confirmed: 'true' });
  });

  it('rejects non-record values', () => {
    expect(toDisplayStringRecord(['not', 'a', 'record'])).toBeUndefined();
    expect(toDisplayStringRecord(null)).toBeUndefined();
  });
});
