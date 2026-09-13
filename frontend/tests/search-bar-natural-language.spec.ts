import { test, expect, type Page } from '@playwright/test';

const mockCrewMembers = [
  {
    id: 'crew-1',
    fullName: 'Dr. Alistair MacIntyre',
    nationality: 'British',
    email: 'alistair@hydenlyne.com',
    phone: '+44 1224 892014',
    availabilityStatus: 'available',
    availabilityDate: null,
    profileCompletenessScore: 92,
    tags: JSON.stringify(['JNCC MMO Certified', 'PAMGUARD', 'Bioacoustics', 'Offshore Wind Mitigation']),
    passport: null,
    visa: null,
    medical: { status: 'fit', expiry: '2027-01-01', provider: 'NHS' },
    insurance: null,
    certifications: [
      { id: 'c1', certType: 'BOSIET', status: 'valid', expiryDate: '2027-05-12' },
      { id: 'c2', certType: 'JNCC MMO', status: 'valid', expiryDate: '2028-03-10' },
      { id: 'c3', certType: 'OGUK Medical', status: 'valid', expiryDate: '2027-01-01' },
    ],
    workHistory: [],
    createdAt: '2025-01-01T00:00:00Z',
    updatedAt: '2025-01-01T00:00:00Z',
  },
  {
    id: 'crew-2',
    fullName: 'Sarah Van Der Berg',
    nationality: 'Dutch',
    email: 'sarah@hydenlyne.com',
    phone: '+44 1202 784300',
    availabilityStatus: 'available',
    availabilityDate: null,
    profileCompletenessScore: 88,
    tags: JSON.stringify(['OBN Quality Control', 'IMCA Survey QC', 'Survey Audit']),
    passport: null,
    visa: null,
    medical: { status: 'fit', expiry: '2027-11-01', provider: 'International SOS' },
    insurance: null,
    certifications: [
      { id: 'c4', certType: 'IMCA Survey QC', status: 'valid', expiryDate: '2026-09-15' },
      { id: 'c5', certType: 'OGUK Medical', status: 'valid', expiryDate: '2027-11-01' },
    ],
    workHistory: [],
    createdAt: '2025-01-01T00:00:00Z',
    updatedAt: '2025-01-01T00:00:00Z',
  },
  {
    id: 'crew-3',
    fullName: 'Richard Chen',
    nationality: 'Dutch',
    email: 'richard@hydenlyne.com',
    phone: '+44 1493 302210',
    availabilityStatus: 'available',
    availabilityDate: null,
    profileCompletenessScore: 85,
    tags: JSON.stringify(['IMCA Client Rep', 'NCS Safety']),
    passport: null,
    visa: null,
    medical: null,
    insurance: null,
    certifications: [
      { id: 'c6', certType: 'IMCA Client Rep', status: 'valid', expiryDate: '2026-12-01' },
    ],
    workHistory: [],
    createdAt: '2025-01-01T00:00:00Z',
    updatedAt: '2025-01-01T00:00:00Z',
  },
];

async function authenticate(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem(
      'hydenlyne_user',
      JSON.stringify({
        id: 'user-1',
        fullName: 'Test Recruiter',
        email: 'recruiter@example.com',
        role: 'admin',
      })
    );
    localStorage.setItem('hydenlyne_theme_preference', 'dark');
  });
}

async function mockGraphQL(page: Page) {
  await page.route('**/health/services', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        services: {
          database: 'healthy',
          redis: 'healthy',
          dropbox: 'healthy',
          ollama: 'healthy',
        },
      }),
    });
  });

  await page.route('**/graphql', async (route) => {
    const body = route.request().postDataJSON() as { query?: string; variables?: Record<string, unknown> };
    const query = body?.query ?? '';

    if (query.includes('query Me')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            me: {
              id: 'user-1',
              fullName: 'Test Recruiter',
              email: 'recruiter@example.com',
              role: 'admin',
            },
          },
        }),
      });
      return;
    }

    if (query.includes('CrewMembers')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            crewMembers: mockCrewMembers,
          },
        }),
      });
      return;
    }

    if (query.includes('QueryCrew')) {
      const q = String(body.variables?.query || '').toLowerCase();
      let matchedCrew = mockCrewMembers;
      let criteria: Record<string, unknown> = {};
      let summary = 'Specialists matching your criteria.';

      if (q.includes('bosiet')) {
        matchedCrew = mockCrewMembers.filter((m) => m.id === 'crew-1');
        criteria = { certifications: ['BOSIET'] };
        summary = '1 specialist found with valid BOSIET certification.';
      } else if (q.includes('imca')) {
        matchedCrew = mockCrewMembers.filter((m) => m.id === 'crew-2' || m.id === 'crew-3');
        criteria = { certification_keywords: ['IMCA'] };
        summary = '2 specialists found with IMCA accreditation.';
      } else if (q.includes('medical')) {
        matchedCrew = mockCrewMembers.filter((m) => m.id === 'crew-1' || m.id === 'crew-2');
        criteria = { medical_required: true, medical_valid: true };
        summary = '2 specialists found with verified offshore medicals.';
      } else if (q.includes('surveyor') || q.includes('available')) {
        matchedCrew = mockCrewMembers;
        criteria = { availability: 'available' };
        summary = '3 available specialists ready for mobilization.';
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            queryCrew: {
              intent: 'search',
              query: body.variables?.query,
              summary,
              results: JSON.stringify(
                matchedCrew.map((m) => ({
                  id: m.id,
                  name: m.fullName,
                  email: m.email,
                  availability: m.availabilityStatus,
                  certifications: m.certifications.map((c) => c.certType),
                }))
              ),
              criteria: JSON.stringify(criteria),
              totalIssues: 0,
              crewId: null,
              crewName: null,
            },
          },
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: {} }),
    });
  });
}

test.describe('Search Bar Natural Language Tests', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await mockGraphQL(page);
  });

  test('executes natural language query "Who has BOSIET certification?" and renders AI criteria & results', async ({ page }) => {
    await page.goto('/');

    const searchInput = page.getByRole('textbox', { name: /search contractors/i });
    await expect(searchInput).toBeVisible();

    // Type query
    await searchInput.fill('Who has BOSIET certification?');
    await searchInput.press('Enter');

    // Verify AI Summary and Criteria chip render
    const interpretationSection = page.locator('section[aria-label="Search interpretation"]');
    await expect(interpretationSection).toBeVisible();
    await expect(interpretationSection.getByRole('button', { name: /Remove BOSIET/i })).toBeVisible();
    await expect(interpretationSection.getByText(/1 specialist found with valid BOSIET certification/i)).toBeVisible();

    // Verify matching contractor is visible in result list
    await expect(page.getByRole('button', { name: /View Dr. Alistair MacIntyre/i })).toBeVisible();
  });

  test('executes query "Find crew with IMCA" and filters to IMCA certified specialists', async ({ page }) => {
    await page.goto('/');

    const searchInput = page.getByRole('textbox', { name: /search contractors/i });
    await searchInput.fill('Find crew with IMCA');
    await searchInput.press('Enter');

    // Verify criteria banner
    const interpretationSection = page.locator('section[aria-label="Search interpretation"]');
    await expect(interpretationSection).toBeVisible();
    await expect(interpretationSection.getByText(/IMCA qualification/i)).toBeVisible();

    // Both Sarah Van Der Berg and Richard Chen hold IMCA qualifications
    await expect(page.getByRole('button', { name: /View Sarah Van Der Berg/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /View Richard Chen/i })).toBeVisible();
  });

  test('executes query "Who has a current medical?" and renders verified medical holders', async ({ page }) => {
    await page.goto('/');

    const searchInput = page.getByRole('textbox', { name: /search contractors/i });
    await searchInput.fill('Who has a current medical?');
    await searchInput.press('Enter');

    // Verify criteria banner has medical requirement
    const interpretationSection = page.locator('section[aria-label="Search interpretation"]');
    await expect(interpretationSection).toBeVisible();
    await expect(interpretationSection.getByText('Current medical')).toBeVisible();

    await expect(page.getByRole('button', { name: /View Dr. Alistair MacIntyre/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /View Sarah Van Der Berg/i })).toBeVisible();
  });

  test('supports recent searches history dropdown and keyboard navigation', async ({ page }) => {
    await page.goto('/');

    const searchInput = page.getByRole('textbox', { name: /search contractors/i });

    // 1. Submit a search to populate recent searches
    await searchInput.fill('Who has BOSIET certification?');
    await searchInput.press('Enter');
    await expect(page.getByRole('button', { name: /View Dr. Alistair MacIntyre/i })).toBeVisible();

    // 2. Clear query using clear button
    const clearButton = page.getByRole('button', { name: /clear search/i });
    await expect(clearButton).toBeVisible();
    await clearButton.click();

    // 3. Focus search input to open Recent Searches menu
    await searchInput.focus();
    await expect(page.getByText(/Recent Searches/i)).toBeVisible();
    await expect(page.getByRole('button', { name: /Who has BOSIET certification\?/i })).toBeVisible();

    // 4. Test keyboard focus shortcut '/'
    await page.keyboard.press('Escape'); // close menu
    await page.mouse.click(10, 10); // unfocus
    await page.keyboard.press('/');
    await expect(searchInput).toBeFocused();
  });

  test('quick discovery chips populate query and trigger search', async ({ page }) => {
    await page.goto('/');

    // Locate the quick discovery chip 'Available Immediately'
    const chip = page.getByRole('button', { name: /Available Immediately/i });
    await expect(chip).toBeVisible();
    await chip.click();

    // Verify query was entered and search was triggered
    const searchInput = page.getByRole('textbox', { name: /search contractors/i });
    await expect(searchInput).toHaveValue('Available immediately');

    // Results workspace should open with matching contractors
    await expect(page.getByRole('button', { name: /View Dr. Alistair MacIntyre/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /View Sarah Van Der Berg/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /View Richard Chen/i })).toBeVisible();
  });
});
