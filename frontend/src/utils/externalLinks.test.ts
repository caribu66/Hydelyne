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
  it('encodes recipient delimiters and the subject', () => {
    expect(mobilizationMailto('crew+ops@example.test?x=1', 'Survey & HSE')).toBe(
      'mailto:crew%2Bops%40example.test%3Fx%3D1?subject=Hydenlyne%20Mobilization%20Request%20-%20Survey%20%26%20HSE',
    );
  });
});
