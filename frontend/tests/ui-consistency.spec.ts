import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('UI consistency', () => {
  test('public shell has no horizontal overflow', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Find the right contractor for the next campaign.' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Open workspace menu' }).getByText('Menu', { exact: true })).toBeVisible();
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
  });

  test('public shell meets automated accessibility checks', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Find the right contractor for the next campaign.' })).toBeVisible();
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });

  test('sign-in dialog meets automated accessibility checks', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Find the right contractor for the next campaign.' })).toBeVisible();
    await page.getByRole('textbox', { name: 'Sign in to search contractors' }).click();
    await expect(page.getByRole('dialog', { name: 'Sign in' })).toBeVisible();
    const results = await new AxeBuilder({ page }).include('[role="dialog"]').analyze();
    expect(results.violations).toEqual([]);
  });

  test('light theme meets automated accessibility checks', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Find the right contractor for the next campaign.' })).toBeVisible();
    await page.getByRole('button', { name: 'Open workspace menu' }).click();
    await page.getByRole('button', { name: 'Use light theme' }).click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
    await expect(page.getByRole('dialog', { name: 'Menu' })).toBeHidden();
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations).toEqual([]);
  });

  test('public shell matches the approved visual baseline', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Find the right contractor for the next campaign.' })).toBeVisible();
    await expect(page.getByText('Private workforce network. Access is protected.')).toBeVisible();
    await expect(page.getByText('Discover')).toBeVisible();
    await expect(page.getByText('Mobilize')).toBeVisible();
    await expect(page).toHaveScreenshot('public-shell.png', { fullPage: true });
  });
});
