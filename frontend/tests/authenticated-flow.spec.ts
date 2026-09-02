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
    localStorage.setItem('hydenlyne_token', 'test-token');
    localStorage.setItem('hydenlyne_user', JSON.stringify({
      id: 'user-1',
      fullName: 'Test Recruiter',
      email: 'recruiter@example.com',
    }));
    localStorage.setItem('hydenlyne_theme_preference', selectedTheme);
  }, theme);
}

async function mockCrewApi(page: Page, options: { crewError?: boolean; member?: typeof crewMember } = {}) {
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
        body: JSON.stringify({ data: { me: { id: 'user-1', fullName: 'Test Recruiter', email: 'recruiter@example.com', role: 'admin' } } }),
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
    await dossier.getByRole('menuitem', { name: 'Technical expertise' }).click();
    await expect(dossier.getByRole('button', { name: 'Expertise', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await expect(dossier.getByText('No explicit expertise section was found in the CV.')).toBeVisible();
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
});
