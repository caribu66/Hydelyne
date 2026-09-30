import { describe, expect, it } from 'vitest';
import { mobilizationMailto, safeLinkedInUrl } from './externalLinks';

describe('safeLinkedInUrl', () => {
  it('accepts HTTPS LinkedIn URLs', () => {
    expect(safeLinkedInUrl('https://www.linkedin.com/in/example', 'Ava Example')).toBe(
      'https://www.linkedin.com/in/example',
    );
  });

  it.each(['javascript:alert(1)', 'https://linkedin.com.evil.test/in/example', 'http://linkedin.com/in/example'])(
    'falls back for unsafe URLs: %s',
    (candidate) => {
      expect(safeLinkedInUrl(candidate, 'Ava Example')).toContain(
        'https://www.linkedin.com/search/results/all/?keywords=Ava%20Example%20Hydenlyne',
      );
    },
  );
});

describe('mobilizationMailto', () => {
  it('keeps a valid recipient intact and encodes only the subject', () => {
    expect(mobilizationMailto('crew+ops@example.test', 'Survey & HSE')).toBe(
      'mailto:crew+ops@example.test?subject=Hydenlyne%20Mobilization%20Request%20-%20Survey%20%26%20HSE',
    );
  });

  it('strips query or fragment smuggled into the stored email', () => {
    expect(mobilizationMailto('crew+ops@example.test?x=1', 'Survey & HSE')).toBe(
      'mailto:crew+ops@example.test?subject=Hydenlyne%20Mobilization%20Request%20-%20Survey%20%26%20HSE',
    );
  });
});
