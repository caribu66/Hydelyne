import { test, expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const crewMember = {
  id: 'crew-1',
  fullName: 'Alex Morgan',
  nationality: 'United Kingdom',
  email: 'alex.morgan@example.com',
  phone: '+44 7000 000000',
  availabilityStatus: 'available',
  availabilityDate: null,
  profileCompletenessScore: 90,
  tags: JSON.stringify(['Hydrography', 'BOSIET', 'Offshore Wind']),
  passport: null,
  visa: null,
  medical: null,
  insurance: null,
  createdAt: '2025-01-01T00:00:00Z',
  updatedAt: '2025-01-01T00:00:00Z',
};

async function authenticate(page: Page, theme: 'dark' | 'light' = 'dark') {
  await page.addInitScript((selectedTheme) => {
    localStorage.setItem('hydenlyne_user', JSON.stringify({
      id: 'user-1',
      fullName: 'Test Recruiter',
      email: 'recruiter@example.com',
    }));
    localStorage.setItem('hydenlyne_theme_preference', selectedTheme);
  }, theme);
}

async function mockCrewApi(page: Page, options: { crewError?: boolean; member?: typeof crewMember; role?: 'admin' | 'staff' | 'user' } = {}) {
  await page.route('**/health/services', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ services: { database: 'healthy', redis: 'healthy', dropbox: 'healthy', ollama: 'healthy' } }),
    });
  });
  await page.route('**/graphql', async (route) => {
    const body = route.request().postDataJSON() as { query?: string };
    const query = body.query ?? '';

    if (query.includes('query Me')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: { me: { id: 'user-1', fullName: 'Test Recruiter', email: 'recruiter@example.com', role: options.role ?? 'admin' } } }),
      });
      return;
    }

    if (query.includes('CrewMembers')) {
      if (options.crewError) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ errors: [{ message: 'Authentication required', extensions: { code: 'UNAUTHENTICATED' } }] }),
        });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: { crewMembers: [options.member ?? crewMember] } }),
      });
      return;
    }

    if (query.includes('query CvReviews')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            cvReviews: [{
              id: 'review-1',
              documentId: 'document-1',
              crewMemberId: 'crew-draft-1',
              status: 'awaiting_review',
              proposedData: JSON.stringify({ full_name: 'Morgan Reed', certifications: ['BOSIET'] }),
              submittedBy: 'staff-1',
              reviewedBy: null,
              reviewNote: null,
              createdAt: '2026-09-05T10:00:00Z',
              reviewedAt: null,
            }],
          },
        }),
      });
      return;
    }

    if (query.includes('query StaffUsers')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: { staffAccounts: [{ id: 'user-2', fullName: 'Jamie Cole', email: 'jamie@example.com', role: 'user' }] } }),
      });
      return;
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: {} }) });
  });
}

test.describe('authenticated specialist workspace', () => {
  test('matches the Hydenlyne workspace baseline', async ({ page }) => {
    await authenticate(page);
    await mockCrewApi(page);
    await page.goto('/?q=hydrography');
    await expect(page.getByRole('button', { name: /View Alex Morgan dossier/ })).toBeVisible();
    await expect(page).toHaveScreenshot('authenticated-workspace.png', { fullPage: true });
  });

  test('matches the Hydenlyne light workspace baseline', async ({ page }) => {
    await authenticate(page, 'light');
    await mockCrewApi(page);
    await page.goto('/?q=hydrography');
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
    await expect(page.getByRole('button', { name: /View Alex Morgan dossier/ })).toBeVisible();
    await expect(page).toHaveScreenshot('authenticated-workspace-light.png', { fullPage: true });
  });

  test('supports keyboard navigation and opening a dossier', async ({ page }) => {
    await authenticate(page);
    await mockCrewApi(page);
    await page.goto('/');

    const search = page.getByRole('textbox', { name: 'Search contractors' });
    await expect(search).toBeVisible();
    await search.fill('hydrography');
    await expect(page.getByRole('button', { name: /View Alex Morgan dossier/ })).toBeVisible();
    await expect(page.locator('mark.search-highlight').first()).toHaveText('Hydrography');

    const resultButton = page.getByRole('button', { name: /View Alex Morgan dossier/ });
    await resultButton.focus();
    await page.keyboard.press('Enter');
    if ((page.viewportSize()?.width ?? 1024) < 768) {
      await expect(page.getByRole('dialog', { name: /Alex Morgan/ })).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(page.getByRole('dialog', { name: /Alex Morgan/ })).toBeHidden();
    } else {
      await expect(page.locator('#specialist-focused-card').getByRole('heading', { name: 'Alex Morgan' })).toBeVisible();
    }
  });

  test('prioritizes dossier reading area in split view', async ({ page }) => {
    test.skip((page.viewportSize()?.width ?? 0) < 768, 'Split view begins at tablet width.');
    await authenticate(page);
    await mockCrewApi(page);
    await page.goto('/?q=hydrography');
    await expect(page.locator('#specialist-focused-card')).toBeVisible();

    const dimensions = await page.locator('.scan-workspace').evaluate((workspace) => {
      const resultList = workspace.querySelector<HTMLElement>('section[aria-label="Contractor search results"]');
      const dossier = workspace.querySelector<HTMLElement>('#specialist-focused-card');
      if (!resultList || !dossier) throw new Error('Split workspace surfaces were not rendered.');

      return {
        dossierWidth: dossier.getBoundingClientRect().width,
        resultListWidth: resultList.getBoundingClientRect().width,
        workspaceHeight: workspace.getBoundingClientRect().height,
        viewportHeight: window.innerHeight,
      };
    });

    expect(dimensions.dossierWidth).toBeGreaterThan(dimensions.resultListWidth);
    if (dimensions.viewportHeight > 800) {
      expect(dimensions.workspaceHeight).toBeGreaterThanOrEqual(
        Math.min(1080, dimensions.viewportHeight - 180),
      );
    }
  });

  test('resizes the split pane with the keyboard, clamps it, and persists the ratio', async ({ page }) => {
    test.skip((page.viewportSize()?.width ?? 0) < 768, 'Split view begins at tablet width.');
    await authenticate(page);
    await mockCrewApi(page);
    await page.goto('/?q=hydrography');
    const splitter = page.getByRole('separator', { name: /Resize results and dossier panes/ });
    await expect(splitter).toBeVisible();

    await splitter.focus();
    const initial = Number(await splitter.getAttribute('aria-valuenow'));

    await page.keyboard.press('ArrowRight');
    await expect(splitter).toHaveAttribute('aria-valuenow', String(initial + 2));

    await page.keyboard.press('End');
    await expect(splitter).toHaveAttribute('aria-valuenow', '60'); // MAX_SPLIT_RATIO
    await page.keyboard.press('ArrowRight'); // clamps, does not exceed the max
    await expect(splitter).toHaveAttribute('aria-valuenow', '60');

    await page.keyboard.press('Home');
    await expect(splitter).toHaveAttribute('aria-valuenow', '25'); // MIN_SPLIT_RATIO

    await splitter.dblclick();
    const afterCycle = await splitter.getAttribute('aria-valuenow');
    expect(afterCycle).not.toBe('25');

    await expect.poll(() =>
      page.evaluate(() => localStorage.getItem('hydenlyne_split_pane_ratio')),
    ).toBe(afterCycle);

    await page.reload();
    await expect(page.getByRole('separator', { name: /Resize results and dossier panes/ })).toHaveAttribute(
      'aria-valuenow',
      afterCycle ?? '',
    );
  });

  test('remains horizontally usable at simulated 200% zoom', async ({ page }) => {
    await authenticate(page);
    await mockCrewApi(page);
    await page.goto('/');

    await page.evaluate(() => {
      document.documentElement.style.zoom = '2';
    });

    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
    await expect(page.getByRole('textbox', { name: 'Search contractors' })).toBeVisible();
  });

  test('opens the themed add-contractor workflow as an accessible dialog', async ({ page }) => {
    await authenticate(page);
    await mockCrewApi(page);
    await page.goto('/');

    await page.getByRole('button', { name: 'Add contractor' }).click();
    const dialog = page.getByRole('dialog', { name: 'Add contractor' });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByLabel('Full name')).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Add contractor', exact: true })).toBeDisabled();
    const accessibility = await new AxeBuilder({ page }).include('[role="dialog"]').analyze();
    expect(accessibility.violations).toEqual([]);
    await dialog.getByRole('button', { name: 'Add contractor', exact: true }).scrollIntoViewIfNeeded();
    const dimensions = await dialog.evaluate((element) => ({ clientHeight: element.clientHeight, scrollHeight: element.scrollHeight }));
    expect(dimensions.clientHeight).toBeLessThanOrEqual(dimensions.scrollHeight);
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
  });

  test('opens an accessible admin CV review with source evidence', async ({ page }) => {
    await authenticate(page);
    await mockCrewApi(page);
    await page.goto('/');

    await page.getByRole('button', { name: 'Open workspace menu' }).click();
    await page.getByRole('button', { name: 'CV submissions' }).click();
    const dialog = page.getByRole('dialog', { name: 'CV submissions' });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('link', { name: 'Open original CV' })).toBeVisible();
    await expect(dialog.getByLabel('Extracted CV information')).toHaveValue(/Morgan Reed/);
    await expect(dialog.getByRole('button', { name: 'Approve and publish' })).toBeVisible();
    const accessibility = await new AxeBuilder({ page }).include('[role="dialog"]').analyze();
    expect(accessibility.violations).toEqual([]);
  });

  test('lets an admin choose which existing accounts become staff', async ({ page }) => {
    await authenticate(page);
    await mockCrewApi(page);
    await page.goto('/');

    await page.getByRole('button', { name: 'Open workspace menu' }).click();
    await page.getByRole('button', { name: 'Staff access' }).click();
    const dialog = page.getByRole('dialog', { name: 'Staff access' });
    await expect(dialog.getByText('Jamie Cole')).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Make staff' })).toBeVisible();
    const accessibility = await new AxeBuilder({ page }).include('[role="dialog"]').analyze();
    expect(accessibility.violations).toEqual([]);
  });

  test('does not grant existing normal users staff submission controls', async ({ page }) => {
    await authenticate(page);
    await mockCrewApi(page, { role: 'user' });
    await page.goto('/');

    await expect(page.getByRole('button', { name: 'Add contractor' })).toHaveCount(0);
    await page.getByRole('button', { name: 'Open workspace menu' }).click();
    await expect(page.getByRole('button', { name: 'CV submissions' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Staff access' })).toHaveCount(0);
  });

  test('provides deterministic filters with removable active criteria', async ({ page }) => {
    await authenticate(page);
    await mockCrewApi(page);
    await page.goto('/');

    await page.getByRole('button', { name: 'More filters' }).click();
    const dialog = page.getByRole('dialog', { name: 'Filter contractors' });
    await expect(dialog).toBeVisible();
    const accessibility = await new AxeBuilder({ page }).include('[role="dialog"]').analyze();
    expect(accessibility.violations).toEqual([]);
    await dialog.getByRole('button', { name: 'Available immediately' }).click();
    await dialog.getByRole('button', { name: /Show 1 contractor/ }).click();
    await expect(page.getByLabel('Active contractor filters')).toContainText('Available immediately');
    await page.getByRole('button', { name: /Remove Status filter/ }).click();
    await expect(page.getByLabel('Active contractor filters')).toHaveCount(0);
  });

  test('exposes accessible names throughout the mobilization request', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await authenticate(page);
    await mockCrewApi(page);
    await page.goto('/?q=hydrography&view=cards');

    await page.getByRole('button', { name: 'More actions for Alex Morgan' }).click();
    await page.getByRole('menuitem', { name: 'Request mobilization' }).click();
    const dialog = page.getByRole('dialog', { name: 'Request mobilization' });
    await expect(dialog.getByLabel('Campaign or vessel')).toBeVisible();
    await expect(dialog.getByLabel('Deployment port')).toBeVisible();
    await expect(dialog.getByLabel('Work required')).toBeVisible();
    await expect(dialog.getByLabel('Preferred start date')).toBeVisible();
    await expect(dialog.getByLabel('Expected duration')).toBeVisible();
    await expect(dialog.getByLabel('Your full name')).toBeVisible();
    const results = await new AxeBuilder({ page }).include('[role="dialog"]').analyze();
    expect(results.violations).toEqual([]);
  });

  test('keeps secondary result actions keyboard accessible without visual clutter', async ({ page }) => {
    await authenticate(page);
    await mockCrewApi(page);
    await page.goto('/?q=hydrography&view=cards');

    const trigger = page.getByRole('button', { name: 'More actions for Alex Morgan' });
    await trigger.focus();
    await page.keyboard.press('Enter');
    const menu = page.getByRole('menu', { name: 'Actions for Alex Morgan' });
    await expect(menu).toBeVisible();
    await expect(menu.getByRole('menuitem', { name: 'Save to shortlist' })).toBeFocused();
    await page.keyboard.press('ArrowDown');
    await expect(menu.getByRole('menuitem', { name: 'Add to compare' })).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(menu).toBeHidden();
    await expect(trigger).toBeFocused();
  });

  test('progressively discloses specialist dossier sections', async ({ page }) => {
    test.skip((page.viewportSize()?.width ?? 0) < 768, 'The mobile dossier uses its compact modal navigation.');
    await authenticate(page);
    await mockCrewApi(page);
    await page.goto('/?q=hydrography');

    const dossier = page.locator('#specialist-focused-card');
    const dossierActions = dossier.getByRole('button', { name: 'More dossier actions for Alex Morgan' });
    await dossierActions.click();
    await expect(dossier.getByRole('menuitem', { name: 'Add to compare' })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(dossierActions).toBeFocused();

    const moreSections = dossier.getByRole('button', { name: 'More', exact: true });
    await moreSections.click();
    await dossier.getByRole('menuitem', { name: 'Systems experience' }).click();
    await expect(dossier.getByRole('button', { name: 'Systems', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await expect(dossier.getByText('No systems experience was found in the CV.')).toBeVisible();
  });

  test('stays usable with unusually long specialist information', async ({ page }) => {
    await authenticate(page);
    await mockCrewApi(page, {
      member: {
        ...crewMember,
        id: 'crew-long-content',
        fullName: 'Alexandria Morgan-Worthington of the North Atlantic Survey Programme',
        email: 'alexandria.morgan-worthington@international-offshore-survey.example.com',
        tags: JSON.stringify(['Hydrography', 'BOSIET', 'Offshore Wind', 'Ultra-Deepwater Geophysical Survey Operations']),
      },
    });
    await page.goto('/?q=hydrography&view=cards');

    await expect(page.getByRole('button', { name: /Open Alexandria Morgan-Worthington/ })).toBeVisible();
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
  });

  test('recovers from an authentication failure during sign-in', async ({ page }) => {
    let loginAttempts = 0;
    await page.route('**/graphql', async (route) => {
      const body = route.request().postDataJSON() as { query?: string };
      if (!(body.query ?? '').includes('mutation Login')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: {} }) });
        return;
      }

      loginAttempts += 1;
      const response = loginAttempts === 1
        ? { success: false, message: 'Invalid email or password', token: null, user: null }
        : { success: true, message: null, token: 'recovered-token', user: { id: 'user-1', fullName: 'Test Recruiter', email: 'recruiter@example.com' } };
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: { login: response } }) });
    });
    await page.goto('/');
    await page.getByRole('button', { name: 'Sign in' }).first().click();
    const dialog = page.getByRole('dialog', { name: 'Sign in' });
    await dialog.getByLabel('Email').fill('recruiter@example.com');
    await dialog.getByRole('textbox', { name: 'Password' }).fill('wrong-password');
    await dialog.getByRole('button', { name: 'Sign in' }).click();
    await expect(dialog.getByRole('alert')).toContainText('Invalid email or password');

    await dialog.getByRole('textbox', { name: 'Password' }).fill('correct-password');
    await dialog.getByRole('button', { name: 'Sign in' }).click();
    await expect(dialog).toBeHidden();
    // Session credentials are HttpOnly; no bearer token is exposed to JS storage.
    await expect.poll(() => page.evaluate(() => localStorage.getItem('hydenlyne_token') || sessionStorage.getItem('hydenlyne_token'))).toBeNull();
  });

  test('returns to signed-out state when the session expires', async ({ page }) => {
    await authenticate(page);
    await mockCrewApi(page, { crewError: true });
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign out' })).toHaveCount(0);
    expect(await page.evaluate(() => localStorage.getItem('hydenlyne_token'))).toBeNull();
  });

  test('closes the document review surface when the session expires', async ({ page }) => {
    await authenticate(page);
    await mockCrewApi(page);
    await page.route('**/api/documents/review-queue', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([{
          id: 'review-1',
          status: 'unread',
          document_id: 'document-1',
          file_name: 'certificate.pdf',
          extraction_status: 'needs_review',
          crew_member_id: 'crew-1',
          contractor_name: 'Alex Morgan',
          created_at: '2026-09-12T10:00:00Z',
        }]),
      });
    });
    await page.goto('/');

    await page.getByRole('button', { name: 'Review documents' }).click();
    await expect(page.getByRole('dialog', { name: 'Documents pending review' })).toBeVisible();

    await page.evaluate(() => window.dispatchEvent(new Event('hydenlyne:session-expired')));
    await expect(page.getByRole('dialog', { name: 'Documents pending review' })).toBeHidden();
  });

  test('signs out to a clean, unfiltered main page without private workspace state', async ({ page }) => {
    await authenticate(page);
    await page.addInitScript(() => {
      localStorage.setItem('hydenlyne_bookmarked_ids', JSON.stringify(['crew-1']));
      localStorage.setItem('hydenlyne_bookmarked_ids:user-1', JSON.stringify(['crew-1']));
    });
    await mockCrewApi(page);
    await page.goto('/?q=hydrography&view=cards');

    await expect(page.getByRole('button', { name: /Open Alex Morgan dossier/ })).toBeVisible();
    await page.getByRole('button', { name: 'Refine filters' }).click();
    const filters = page.getByRole('dialog', { name: 'Filter contractors' });
    await filters.getByRole('button', { name: 'Available immediately' }).click();
    await filters.getByRole('button', { name: /Show 1 contractor/ }).click();
    await expect(page.getByLabel('Active contractor filters')).toContainText('Available immediately');

    await page.getByRole('button', { name: 'Open workspace menu' }).click();
    await page.getByRole('button', { name: 'Sign out' }).click();

    await expect(page).toHaveURL('/');
    await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: /Open Alex Morgan dossier/ })).toHaveCount(0);
    await expect(page.getByLabel('Active contractor filters')).toHaveCount(0);
    await expect.poll(() => page.evaluate(() => localStorage.getItem('hydenlyne_bookmarked_ids'))).toBe('[]');
    await expect.poll(() => page.evaluate(() => localStorage.getItem('hydenlyne_bookmarked_ids:user-1'))).toBeNull();
    await expect.poll(() => page.evaluate(() => localStorage.getItem('hydenlyne_token'))).toBeNull();
  });
});
