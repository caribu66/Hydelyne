import { describe, expect, it } from 'vitest';
import { visibleDossierItems } from './dossierUtils';

describe('visibleDossierItems', () => {
  it('keeps dense lists scannable until the agent expands them', () => {
    expect(visibleDossierItems(['one', 'two', 'three', 'four'], false, 2)).toEqual(['one', 'two']);
  });

  it('returns every record after expansion and does not hide small lists', () => {
    expect(visibleDossierItems(['one', 'two', 'three'], true, 2)).toEqual(['one', 'two', 'three']);
    expect(visibleDossierItems(['one', 'two'], false, 2)).toEqual(['one', 'two']);
  });
});
