import { describe, expect, it } from 'vitest';
import { csvCell, csvDocument } from './csv';

describe('csv export boundaries', () => {
  it('quotes delimiters, quotes, and newlines', () => {
    expect(csvCell('A, "quoted"\nvalue')).toBe('"A, ""quoted""\nvalue"');
  });

  it('neutralizes spreadsheet formula prefixes', () => {
    expect(csvCell('=HYPERLINK("https://example.test")')).toBe(
      '"\'=HYPERLINK(""https://example.test"")"',
    );
  });

  it('builds rows with stable CSV delimiters', () => {
    expect(csvDocument([['Name', 'Email'], ['Ava, Example', 'ava@example.test']])).toBe(
      '"Name","Email"\n"Ava, Example","ava@example.test"',
    );
  });
});
