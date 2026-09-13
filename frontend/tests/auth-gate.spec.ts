import { test, expect, type Page } from '@playwright/test';

// Regression coverage for a bug class, not just one instance: a deep link
// that seeds search/filter state via the URL (?q=, ?view=, and any future
// param) must never render result-bearing UI, or fire a data-fetching
// GraphQL operation, for an unauthenticated visitor — it must fall back to
// the same public calm shell a plain unauthenticated visit shows. See
// `isSearchActive` in `src/hooks/useSearchWorkspace.ts` for the render-time
// gate this asserts against, and `docs/ARCHITECTURE.md`'s Security
// boundaries section for the rule. The sign-in dialog itself only opens on
// user interaction (clicking the disabled search box) — a URL-seeded query
// deliberately does not auto-open it, since doing so previously raced the
// async session check on mount and could pop the dialog open for an
// already-authenticated deep-linked visit and leave it stuck.

const GATED_OPERATIONS = ['CrewMembers', 'QueryCrew', 'SearchCrew'];

async function collectGraphQLOperations(page: Page): Promise<string[]> {
  const seen: string[] = [];
  page.on('request', (request) => {
    if (!request.url().includes('/graphql')) return;
    const data = request.postData();
    if (!data) return;
    try {
      const body = JSON.parse(data) as { query?: string };
      const match = body.query?.match(/(?:query|mutation)\s+(\w+)/);
      seen.push(match?.[1] ?? body.query ?? '');
    } catch {
      // Non-JSON body; ignore.
    }
  });
  return seen;
}

test.describe('unauthenticated deep links never reveal gated search UI', () => {
  for (const path of ['/?q=hele', '/?view=table', '/?q=hele&view=table']) {
    test(`${path} renders the public shell without results chrome`, async ({ page }) => {
      const operations = await collectGraphQLOperations(page);

      await page.goto(path);

      await expect(page.getByRole('textbox', { name: 'Sign in to search contractors' })).toBeVisible();
      await expect(page.getByText(/Found \d+ contractor/)).toHaveCount(0);
      await expect(page.getByRole('combobox', { name: 'Sort contractors' })).toHaveCount(0);
      await expect(page.getByRole('region', { name: 'Contractor search results' })).toHaveCount(0);
      for (const gated of GATED_OPERATIONS) {
        expect(operations, `${gated} must not fire for an unauthenticated visitor`).not.toContain(gated);
      }
    });
  }

  test('clicking the disabled search box still opens the sign-in dialog with a ?q= link', async ({ page }) => {
    await page.goto('/?q=hele');
    await page.getByRole('textbox', { name: 'Sign in to search contractors' }).click();
    await expect(page.getByRole('dialog', { name: 'Sign in' })).toBeVisible();
  });

  test('public shell clears private recent search history after logout', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('hydenlyne_recent_searches', JSON.stringify(['private contractor query']));
    });

    await page.goto('/');

    await expect(page.getByText(/Recent Searches/i)).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => localStorage.getItem('hydenlyne_recent_searches'))).toBeNull();
  });
});
