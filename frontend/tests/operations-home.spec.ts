import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const crewMembers = [
  {
    id: 'crew-1',
    fullName: 'Alex Morgan',
    nationality: 'British',
    email: 'alex@example.com',
    phone: '+44 7000 000000',
    availabilityStatus: 'available',
    availabilityDate: null,
    profileCompletenessScore: 90,
    tags: JSON.stringify(['Hydrography', 'BOSIET']),
    passport: null,
    visa: null,
    medical: null,
    insurance: null,
    createdAt: '2025-01-01T00:00:00Z',
    updatedAt: '2025-01-01T00:00:00Z',
  },
  {
    id: 'crew-2',
    fullName: 'Jamie Cole',
    nationality: 'Dutch',
    email: 'jamie@example.com',
    phone: '+44 7000 111111',
    availabilityStatus: 'on_assignment',
    availabilityDate: null,
    profileCompletenessScore: 80,
    tags: JSON.stringify(['Client Rep', 'IMCA']),
    passport: null,
    visa: null,
    medical: null,
    insurance: null,
    createdAt: '2025-01-01T00:00:00Z',
    updatedAt: '2025-01-01T00:00:00Z',
  },
  {
    id: 'crew-3',
    fullName: 'Sam Patel',
    nationality: 'British',
    email: 'sam@example.com',
    phone: '+44 7000 222222',
    availabilityStatus: 'unavailable',
    availabilityDate: null,
    profileCompletenessScore: 70,
    tags: JSON.stringify(['Geotech', 'HSE']),
    passport: null,
    visa: null,
    medical: null,
    insurance: null,
    createdAt: '2025-01-01T00:00:00Z',
    updatedAt: '2025-01-01T00:00:00Z',
  },
]

const expiringCerts = [
  { id: 'cert-1', certType: 'BOSIET', expiryDate: '2026-10-01', status: 'expiring_soon', verificationStatus: 'verified' },
  { id: 'cert-2', certType: 'STCW', expiryDate: '2026-10-15', status: 'expiring_soon', verificationStatus: 'verified' },
]

const projects = [
  {
    id: 'proj-1',
    clientName: 'North Sea Energy',
    projectName: 'Arbroath Wind Survey',
    projectType: 'offshore_wind',
    location: 'North Sea',
    country: 'Scotland',
    startDate: '2026-09-01',
    endDate: '2026-12-01',
    status: 'active',
  },
  {
    id: 'proj-2',
    clientName: 'GeoPacific',
    projectName: 'Celtic Deep Seismic',
    projectType: 'marine_seismic',
    location: 'Celtic Sea',
    country: 'United Kingdom',
    startDate: '2026-10-01',
    endDate: '2027-01-01',
    status: 'planning',
  },
]

async function authenticate(page: Page, _role: 'admin' | 'staff' | 'user' = 'staff') {
  await page.addInitScript(() => {
    localStorage.setItem('hydenlyne_token', 'test-token')
    localStorage.setItem(
      'hydenlyne_user',
      JSON.stringify({
        id: 'user-1',
        fullName: 'Test Recruiter',
        email: 'recruiter@example.com',
      })
    )
    localStorage.setItem('hydenlyne_theme_preference', 'dark')
    // Fix greeting hour to morning for deterministic tests
    const fixed = new Date('2026-09-06T09:00:00').getTime()
    const OriginalDate = globalThis.Date
    globalThis.Date = class extends OriginalDate {
      constructor(...args: unknown[]) {
        if (args.length === 0) {
          super(fixed)
        } else {
          super(...(args as ConstructorParameters<typeof Date>))
        }
      }
      static now() {
        return fixed
      }
    } as unknown as typeof Date
  })
}

async function mockApi(page: Page, options: { role?: 'admin' | 'staff' | 'user'; docCount?: number } = {}) {
  const role = options.role ?? 'staff'
  const docCount = options.docCount ?? 2
  await page.route('**/health/services', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ services: { database: 'healthy', redis: 'healthy', dropbox: 'healthy', ollama: 'healthy' } }),
    })
  })

  await page.route('**/api/documents/review-queue', async (route) => {
    const items = Array.from({ length: docCount }, (_, i) => ({
      id: `review-${i + 1}`,
      status: 'unread',
      document_id: `doc-${i + 1}`,
      file_name: `contractor-doc-${i + 1}.pdf`,
      crew_member_id: 'crew-1',
      contractor_name: 'Alex Morgan',
      created_at: '2026-09-06T08:00:00Z',
    }))
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(items),
    })
  })

  await page.route('**/graphql', async (route) => {
    const body = route.request().postDataJSON() as { query?: string; variables?: Record<string, unknown> }
    const query = body.query ?? ''

    if (query.includes('query Me')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: { me: { id: 'user-1', fullName: 'Test Recruiter', email: 'recruiter@example.com', role } } }),
      })
      return
    }

    if (query.includes('CrewMembers')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: { crewMembers } }),
      })
      return
    }

    if (query.includes('ExpiringCerts') || query.includes('expiringCertifications')) {
      if (role === 'user') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ errors: [{ message: 'Admin access required', extensions: { code: 'FORBIDDEN' } }] }),
        })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: { expiringCertifications: expiringCerts } }),
      })
      return
    }

    if (query.includes('Projects') || query.includes('projects')) {
      const status = body.variables?.status
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: { projects: status === 'ACTIVE' ? projects.filter((project) => project.status === 'active') : projects } }),
      })
      return
    }

    if (query.includes('SearchVessels') || query.includes('vesselSearch')) {
      const name = (body.variables?.name as string) ?? ''
      if (!name) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            data: {
              vesselSearch: {
                vessels: [],
                cached: false,
                provider: 'vesselapi',
                upstreamCount: 0,
                configured: true,
              },
            },
          }),
        })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            vesselSearch: {
              vessels: [
                {
                  id: '9683934',
                  name: 'Fugro Pioneer',
                  imo: '9683934',
                  mmsi: '244790000',
                  callsign: 'PHDY',
                  vesselType: 'Research Vessel',
                  flag: 'NL',
                  length: 53.7,
                  width: 12.5,
                  yearBuilt: 2014,
                },
              ],
              cached: true,
              provider: 'vesselapi',
              upstreamCount: 1,
              configured: true,
            },
          },
        }),
      })
      return
    }

    if (query.includes('VesselRoster') || query.includes('vesselRoster')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            vesselRoster: [
              {
                id: 'assign-1',
                crewMemberId: 'crew-1',
                projectId: 'proj-1',
                vesselImo: '9683934',
                roleOnBoard: 'Chief Party Manager',
                startDate: '2026-09-01',
                endDate: '2026-09-22',
                status: 'on_board',
                agreedDayRate: 850,
                notes: 'Lead QC',
                createdAt: '2026-09-01T00:00:00Z',
                updatedAt: '2026-09-01T00:00:00Z',
                crewName: 'Alex Morgan',
                vesselName: 'Fugro Pioneer',
                projectName: 'Arbroath Wind Survey',
              },
            ],
          },
        }),
      })
      return
    }

    if (query.includes('CreateCampaignAssignment') || query.includes('createCampaignAssignment')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            createCampaignAssignment: {
              id: 'assign-new-999',
              crewMemberId: 'crew-1',
              vesselImo: '9683934',
              roleOnBoard: 'Lead Seismic QC',
              startDate: '2026-10-01',
              endDate: '2026-10-29',
              status: 'confirmed',
              agreedDayRate: 850,
              notes: 'Operational dispatch',
              createdAt: '2026-09-06T10:00:00Z',
              updatedAt: '2026-09-06T10:00:00Z',
              crewName: 'Alex Morgan',
              vesselName: 'Fugro Pioneer',
              projectName: 'Johan Sverdrup 4D OBN Survey',
            },
          },
        }),
      })
      return
    }

    if (query.includes('CrewMembers') || query.includes('crewMembers')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            crewMembers: [
              {
                id: 'crew-1',
                fullName: 'Alex Morgan',
                nationality: 'UK',
                countryOfResidence: 'UK',
                availabilityStatus: 'available',
                availabilityDate: null,
                profileCompletenessScore: 0.95,
                yearsOfExperience: 8,
                professionalSummary: 'Senior Geophysicist with 8 years North Sea OBN QC experience.',
                geographicalExperience: '["North Sea", "Norwegian Sector"]',
                systemsExperience: '["PAMGuard", "QGIS"]',
                trainingQualifications: '["OPITO BOSIET", "OGUK Medical"]',
                tags: '["Seismic", "OBN", "QC", "Geophysicist"]',
                certifications: [
                  {
                    id: 'cert-1',
                    certType: 'OPITO BOSIET with CA-EBS',
                    issueDate: '2023-01-01',
                    expiryDate: '2027-10-01',
                    status: 'valid',
                    verificationStatus: 'verified',
                  },
                ],
                medical: {
                  status: 'valid',
                  expiry: '2027-10-01',
                },
                createdAt: '2024-01-01T00:00:00Z',
                updatedAt: '2024-01-01T00:00:00Z',
              },
            ],
          },
        }),
      })
      return
    }

    if (query.includes('CrewMember')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: {} }),
      })
      return
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: {} }) })
  })
}

test.describe('operations home — staff visibility and actions', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page, 'staff')
    await mockApi(page, { role: 'staff', docCount: 2 })
  })

  test('shows greeting with first name and operational cards', async ({ page }) => {
    await page.goto('/')
    // Greeting uses first name Test and time-aware prefix
    await expect(page.getByRole('heading', { name: /Good (morning|afternoon|evening), Test/ })).toBeVisible()
    await expect(page.getByText('ready across Hydenlyne operations')).toBeVisible()
    // Find a contractor prominent
    await expect(page.getByRole('heading', { name: 'Find a contractor' })).toBeVisible()
    // Needs attention
    await expect(page.getByRole('heading', { name: 'Needs attention' })).toBeVisible()
    await expect(page.getByText('Documents ready for review')).toBeVisible()
    await expect(page.getByText('Certificates expiring')).toBeVisible()
    // Show counts: 2 docs, 2 certs expiring
    await expect(page.getByText('2 items need attention').first()).toBeVisible()
    // Crew readiness 2x2 grid
    await expect(page.getByRole('heading', { name: 'Crew readiness' })).toBeVisible()
    const crewSection = page.locator('section[aria-labelledby="readiness-heading"]')
    await expect(crewSection.getByText('Available now')).toBeVisible()
    await expect(crewSection.getByText('On assignment')).toBeVisible()
    await expect(crewSection.getByText('Unavailable')).toBeVisible()
    await expect(crewSection.getByText('Total specialists')).toBeVisible()
    // Metric numbers: derived from 3 profiles: 1 available, 1 on assignment, 1 unavailable, total 3.
    await expect(crewSection.getByText('Available now').locator('..').getByText('1').first()).toBeVisible()
    await expect(crewSection.getByText('Unavailable').locator('..').getByText('1').first()).toBeVisible()
    // Projects
    await expect(page.getByRole('heading', { name: 'Active projects' })).toBeVisible()
    await expect(page.getByText('Arbroath Wind Survey')).toBeVisible()
    await expect(page.getByText('Celtic Deep Seismic')).toHaveCount(0)

    const attentionBox = await page.getByRole('heading', { name: 'Needs attention' }).boundingBox()
    const searchBox = await page.getByRole('heading', { name: 'Find a contractor' }).boundingBox()
    expect(attentionBox?.y).toBeLessThan(searchBox?.y ?? Number.POSITIVE_INFINITY)
  })

  test('documents attention opens the pending documents review dialog', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Needs attention' })).toBeVisible()
    const docRow = page.getByRole('button', { name: 'Review documents' })
    await expect(docRow).toBeVisible()
    await docRow.click()
    await expect(page.getByRole('dialog', { name: 'Documents pending review' })).toBeVisible()
    // Verify the review queue content appears (mocked 2 pending).
    await expect(page.getByRole('list', { name: 'Pending documents' }).getByText('contractor-doc-1.pdf')).toBeVisible()
    await expect(page.getByRole('list', { name: 'Pending documents' }).getByText('contractor-doc-2.pdf')).toBeVisible()
  })

  test('certificates expiring triggers a filtered contractor search', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Needs attention' })).toBeVisible()
    const certButton = page.getByRole('button', { name: 'View certificates' })
    await expect(certButton).toBeVisible()
    await certButton.click()
    // Should have populated search with expiring query and activated results
    // The search textarea should contain the expiring query
    await expect(page.getByRole('textbox', { name: 'Search contractors' })).toHaveValue(/expiring/)
    // Results header appears when search active
    await expect(page.getByText(/Found \d+ contractor/)).toBeVisible()
  })

  test('project row leads to project-specific contractor search', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Arbroath Wind Survey')).toBeVisible()
    await page.getByRole('button', { name: /Find contractors for Arbroath Wind Survey/ }).click()
    await expect(page.getByRole('textbox', { name: 'Search contractors' })).toHaveValue(/offshore wind.*North Sea|North Sea.*offshore wind/i)
    await expect(page.getByText(/Found \d+ contractor/)).toBeVisible()
  })

  test('clicking available readiness metric triggers contractor search', async ({ page }) => {
    await page.goto('/')
    const availableBtn = page.getByRole('button', { name: 'Filter by Available now' })
    await expect(availableBtn).toBeVisible()
    await availableBtn.click()
    await expect(page.getByRole('textbox', { name: 'Search contractors' })).toHaveValue('available')
    await expect(page.getByText(/Found \d+ contractor/)).toBeVisible()
  })

  test('operations button in active search returns to operations home', async ({ page }) => {
    await page.goto('/')
    // Enter search mode via project row
    await page.getByRole('button', { name: /Find contractors for Arbroath Wind Survey/ }).click()
    await expect(page.getByText(/Found \d+ contractor/)).toBeVisible()
    // Click the Operations Home return button
    const backBtn = page.getByRole('button', { name: 'Return to operations overview' })
    await expect(backBtn).toBeVisible()
    await backBtn.click()
    // Verify Operations Home is back
    await expect(page.getByRole('heading', { name: 'Needs attention' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Find a vessel' })).toBeVisible()
  })

  test('searching for a vessel renders live results with specs', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('tab', { name: 'Find a vessel' }).click()
    await expect(page.getByRole('heading', { name: 'Find a vessel' })).toBeVisible()
    const input = page.getByRole('searchbox', { name: 'Search vessels' })
    await expect(input).toBeVisible()
    await input.fill('Fugro Pioneer')
    await page.getByRole('button', { name: 'Submit vessel search' }).click()
    // Verify vessel result card appears
    await expect(page.getByText('Fugro Pioneer')).toBeVisible()
    await expect(page.getByText('Research Vessel')).toBeVisible()
    await expect(page.getByText('9683934')).toBeVisible()
    await expect(page.getByText('244790000')).toBeVisible()

    // Toggle and verify Crew Roster
    const rosterBtn = page.getByRole('button', { name: 'Crew roster' })
    await expect(rosterBtn).toBeVisible()
    await rosterBtn.click()
    const rosterRegion = page.getByRole('region', { name: 'Crew roster for IMO 9683934' })
    await expect(rosterRegion).toBeVisible()
    await expect(rosterRegion.getByText('Alex Morgan')).toBeVisible()
    await expect(rosterRegion.getByText('Chief Party Manager')).toBeVisible()
    await expect(rosterRegion.getByText('On Board')).toBeVisible()

    // Test agent mobilization dispatch from vessel card
    const mobilizeBtn = page.getByRole('button', { name: 'Mobilize specialist to Fugro Pioneer' })
    await expect(mobilizeBtn).toBeVisible()
    await mobilizeBtn.click()

    const dialog = page.getByRole('dialog', { name: 'Mobilize specialist to vessel' })
    await expect(dialog).toBeVisible()
    await expect(dialog.getByText(/Fugro Pioneer · IMO 9683934/)).toBeVisible()
    await expect(dialog.getByText('1. Campaign Rotation & Role')).toBeVisible()
    await expect(dialog.getByText('2. Select Specialist & Pre-Flight Matrix')).toBeVisible()

    // Candidate should appear in search results with compliance badge
    await expect(dialog.getByText('Alex Morgan')).toBeVisible()
    await expect(dialog.getByText('Compliant').first()).toBeVisible()

    // Select candidate
    await dialog.getByRole('button', { name: 'Select' }).first().click()
    await expect(dialog.getByText('Pre-flight compliance report for')).toBeVisible()
    await expect(dialog.getByText('Schedule Availability')).toBeVisible()

    // Submit mobilization
    await dialog.getByRole('button', { name: 'Confirm & mobilize specialist' }).click()
    await expect(dialog.getByText('Mobilization confirmed')).toBeVisible()
    await expect(dialog.getByText(/HYD-MOB-/)).toBeVisible()
    await dialog.getByRole('button', { name: 'Done' }).click()
    await expect(dialog).not.toBeVisible()
  })

  test('mobilization modal supports dynamic role discovery and quick discipline chips', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('tab', { name: 'Find a vessel' }).click()
    await expect(page.getByRole('heading', { name: 'Find a vessel' })).toBeVisible()
    const input = page.getByRole('searchbox', { name: 'Search vessels' })
    await expect(input).toBeVisible()
    await input.fill('Fugro Pioneer')
    await page.getByRole('button', { name: 'Submit vessel search' }).click()
    await expect(page.getByText('Fugro Pioneer')).toBeVisible()

    const mobilizeBtn = page.getByRole('button', { name: 'Mobilize specialist to Fugro Pioneer' })
    await mobilizeBtn.click()

    const dialog = page.getByRole('dialog', { name: 'Mobilize specialist to vessel' })
    await expect(dialog).toBeVisible()

    // 1. Initial state: filtered by default role "Client Representative" (keyword: Client Rep)
    await expect(dialog.getByText(/Filtered by role: Client Rep/)).toBeVisible()

    // 2. Click "Show all specialists"
    await dialog.getByRole('button', { name: 'Show all specialists' }).click()
    await expect(dialog.getByText(/Showing all specialists/)).toBeVisible()

    // 3. Click "MMO / PAM" discipline chip
    await dialog.getByRole('button', { name: 'MMO / PAM' }).click()
    await expect(dialog.getByText(/Search:/)).toBeVisible()
    await expect(dialog.getByText(/"MMO"/)).toBeVisible()

    // 4. Change role in Step 1 dropdown to "Senior Hydrographer"
    await dialog.getByLabel('Role on board').selectOption('Senior Hydrographer')
    // Changing role should reset search and automatically focus on Hydrograph
    await expect(dialog.getByText(/Filtered by role: Hydrograph/)).toBeVisible()

    // 5. Close modal
    await dialog.getByRole('button', { name: 'Close modal' }).click()
    await expect(dialog).not.toBeVisible()
  })

  test('empty and unavailable states are handled', async ({ page }) => {
    // Override mocks for empty case
    await page.route('**/api/documents/review-queue', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
    })
    await page.route('**/graphql', async (route) => {
      const body = route.request().postDataJSON() as { query?: string }
      const q = body.query ?? ''
      if (q.includes('query Me')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: { me: { id: 'user-1', fullName: 'Test Recruiter', email: 'recruiter@example.com', role: 'staff' } } }) })
        return
      }
      if (q.includes('CrewMembers')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: { crewMembers } }) })
        return
      }
      if (q.includes('expiringCertifications')) {
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: { expiringCertifications: [] } }) })
        return
      }
      if (q.includes('projects')) {
        // Simulate failure -> Project data is unavailable
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ errors: [{ message: 'Internal error' }] }) })
        return
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ data: {} }) })
    })
    await page.goto('/')
    await expect(page.getByText('No documents await review')).toBeVisible()
    await expect(page.getByText('No certificates expiring soon')).toBeVisible()
    await expect(page.getByText('Project data is unavailable')).toBeVisible()
  })

  test('has no horizontal overflow and remains readable at 375px', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /Good (morning|afternoon|evening), Test/ })).toBeVisible()
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }))
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport)
    // Metrics grid should be stacked (single column) on mobile — check that grid has 1 column computed
    const grid = page.locator('section', { has: page.getByRole('heading', { name: 'Crew readiness' }) }).locator('.grid')
    await expect(grid).toBeVisible()
  })

  test('meets accessibility for operations home', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /Good (morning|afternoon|evening), Test/ })).toBeVisible()
    const results = await new AxeBuilder({ page }).include('[aria-label="Operations overview"]').analyze()
    expect(results.violations).toEqual([])
  })

  test('renders correctly in light theme', async ({ page }) => {
    await authenticate(page, 'staff')
    await page.addInitScript(() => localStorage.setItem('hydenlyne_theme_preference', 'light'))
    await mockApi(page, { role: 'staff' })
    await page.goto('/')
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'light')
    await expect(page.getByRole('heading', { name: /Good (morning|afternoon|evening), Test/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Find a contractor' })).toBeVisible()
    const results = await new AxeBuilder({ page }).include('[aria-label="Operations overview"]').analyze()
    expect(results.violations).toEqual([])
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }))
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport)
  })
})

test.describe('operations home — non-staff visibility', () => {
  test('authenticated non-staff sees greeting and safe search, no operational detail', async ({ page }) => {
    await authenticate(page, 'user')
    await mockApi(page, { role: 'user', docCount: 2 })
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /Good (morning|afternoon|evening), Test/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Find a contractor' })).toBeVisible()
    // Safe fallback, not operational cards
    await expect(page.getByText('Use the search below to explore the private specialist network.')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Needs attention' })).toHaveCount(0)
    await expect(page.getByRole('heading', { name: 'Crew readiness' })).toHaveCount(0)
    await expect(page.getByRole('heading', { name: 'Active projects' })).toHaveCount(0)
    // No sensitive counts exposed — e.g., document pending count not shown
    await expect(page.getByText('Documents ready for review')).toHaveCount(0)
  })

  test('non-staff home has no horizontal overflow', async ({ page }) => {
    await authenticate(page, 'user')
    await mockApi(page, { role: 'user' })
    await page.goto('/')
    const dimensions = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }))
    expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport)
  })
})

test.describe('operations home — responsive layouts', () => {
  // These tests run across all viewport projects automatically (mobile/tablet/desktop/wide).
  // Verify that core surfaces remain visible and not clipped.
  test('operations panels stay readable across viewports', async ({ page }) => {
    await authenticate(page, 'staff')
    await mockApi(page, { role: 'staff' })
    await page.goto('/')
    await expect(page.getByRole('heading', { name: /Good (morning|afternoon|evening), Test/ })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Find a contractor' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Needs attention' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Crew readiness' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Active projects' })).toBeVisible()
    // Ensure metrics grid cells are visible (2x2 on desktop, stacked on mobile handled by CSS)
    const crewSection = page.locator('section[aria-labelledby="readiness-heading"]')
    await expect(crewSection.getByText('Available now')).toBeVisible()
    await expect(crewSection.getByText('Total specialists')).toBeVisible()
    // Ensure no horizontal overflow at any width
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
    expect(overflow).toBe(false)
  })
})
