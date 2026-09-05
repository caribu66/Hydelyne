import { defineConfig, devices } from '@playwright/test';

const playwrightPort = process.env.PLAYWRIGHT_PORT ?? '3000';
const playwrightBaseURL = `http://127.0.0.1:${playwrightPort}`;

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: [['html', { open: 'never' }], ['line']],
  use: {
    baseURL: playwrightBaseURL,
    trace: 'on-first-retry',
    colorScheme: 'dark',
    // Framer Motion drives most animations via transform/opacity outside
    // CSS, so `expect.toHaveScreenshot`'s `animations: 'disabled'` (which
    // only freezes CSS animations/transitions) doesn't stop them — screenshot
    // tests were capturing mid-animation, non-deterministic frames.
    // MotionConfig reducedMotion="user" (src/main.tsx) makes the app honor
    // this the same way it already honors prefers-reduced-motion in CSS.
    contextOptions: { reducedMotion: 'reduce' },
  },
  webServer: {
    command: `npm run dev -- --host 127.0.0.1 --port ${playwrightPort}`,
    url: playwrightBaseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
  projects: [
    { name: 'mobile', use: { ...devices['iPhone 13'], browserName: 'chromium' } },
    { name: 'tablet', use: { ...devices['iPad Mini'], browserName: 'chromium' } },
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'wide', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1000 } } },
  ],
  expect: {
    toHaveScreenshot: {
      animations: 'disabled',
      caret: 'hide',
      scale: 'css',
      maxDiffPixels: 0,
    },
  },
});
