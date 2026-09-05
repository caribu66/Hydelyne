import { UserProfile, AvailabilityStatus, RemoteType } from '../types'

export type BackendCrew = {
  id: string
  fullName: string
  nationality?: string | null
  countryOfResidence?: string | null
  dateOfBirth?: string | null
  gender?: string | null
  languages?: string[] | string | null
  flyingPoint?: string | null
  email?: string | null
  phone?: string | null
  availabilityStatus?: string
  availabilityDate?: string | null
  profileCompletenessScore?: number | null
  yearsOfExperience?: number | null
  education?: string | null
  professionalSummary?: string | null
  geographicalExperience?: string | null
  systemsExperience?: string | null
  trainingQualifications?: string | null
  certifications?: Array<{ id: string; certType: string; certNumber?: string | null; issuingBody?: string | null; issueDate?: string | null; expiryDate?: string | null; renewalDate?: string | null; status?: string | null; verificationStatus?: string | null }> | null
  workHistory?: Array<{ id: string; clientName?: string | null; projectName?: string | null; projectType?: string | null; location?: string | null; country?: string | null; role?: string | null; responsibilities?: string | null; startDate?: string | null; endDate?: string | null; status?: string | null }> | null
  tags?: string | null // JSON string
  passport?: { number?: string | null; expiry?: string | null; issuingCountry?: string | null } | null
  visa?: { type?: string | null; expiry?: string | null } | null
  medical?: { status?: string | null; expiry?: string | null } | null
  createdAt?: string
  updatedAt?: string
}

function mapAvailability(status?: string): AvailabilityStatus {
  switch (status) {
    case 'available':
      return 'Available immediately'
    case 'on_assignment':
      return 'Employed (Not looking)'
    case 'unavailable':
      return 'Open to offers'
    default:
      return 'Available immediately'
  }
}

// Curated showcase portraits shared by the demo roster and used as a stable
// visual fallback for live records that do not yet contain a profile photo.
const SHOWCASE_AVATARS = [
  'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=240&h=240&fit=crop&crop=faces&q=85',
  'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=240&h=240&fit=crop&crop=faces&q=85',
  'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=240&h=240&fit=crop&crop=faces&q=85',
  'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=240&h=240&fit=crop&crop=faces&q=85',
  'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=240&h=240&fit=crop&crop=faces&q=85',
  'https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=240&h=240&fit=crop&crop=faces&q=85',
  'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=240&h=240&fit=crop&crop=faces&q=85',
  'https://images.unsplash.com/photo-1580489944761-15a19d654956?w=240&h=240&fit=crop&crop=faces&q=85',
  'https://images.unsplash.com/photo-1522075469751-3a6694fb2f61?w=240&h=240&fit=crop&crop=faces&q=85',
  'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=240&h=240&fit=crop&crop=faces&q=85',
  'https://images.unsplash.com/photo-1501196354995-cbb51c65aaea?w=240&h=240&fit=crop&crop=faces&q=85',
  'https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?w=240&h=240&fit=crop&crop=faces&q=85',
  'https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?w=240&h=240&fit=crop&crop=faces&q=85',
  'https://images.unsplash.com/photo-1567532939604-b6b5b0db2604?w=240&h=240&fit=crop&crop=faces&q=85',
]

function avatarFor(name: string): string {
  const seed = name.trim().toLowerCase()
  let hash = 0
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) | 0
  return SHOWCASE_AVATARS[Math.abs(hash) % SHOWCASE_AVATARS.length] ?? SHOWCASE_AVATARS[0] ?? ''
}

function departmentFromTags(tags: string[]): string {
  if (tags.some((t) => /mmo|pam|environmental/i.test(t))) return 'Marine Environmental'
  if (tags.some((t) => /seismic|geophys|qc/i.test(t))) return 'Geophysical & Survey QC'
  if (tags.some((t) => /geotech|cpt|cable/i.test(t))) return 'Geotechnical & Subsea'
  if (tags.some((t) => /hse|fl[oe]/i.test(t))) return 'HSE & Safety Advisory'
  return 'Survey, HSE & Client Rep'
}

function normalizeTraining(values: string[]): Array<{ id: string; name: string; location?: string; completedDate?: string; expiryDate?: string }> {
  const LOCATION_TOKENS = new Set([
    'Poland', 'UK', 'Norway', 'Szczecin', 'Inverness', 'Weston-super-Mare', 'Edinburgh', 'Grimstad', 'Aberdeen', 'GeoPacific',
  ])
  const isLocation = (s: string) => LOCATION_TOKENS.has(s.trim())
  const isStatusLine = (s: string) =>
    /^Completed\s+\d{4}/i.test(s) || /^Expires\s+\d{4}/i.test(s) || /Completion date not recorded/i.test(s)

  const results: Array<{ id: string; name: string; location?: string; completedDate?: string; expiryDate?: string }> = []
  let nameParts: string[] = []
  let location: string | undefined
  let completedYear: string | undefined
  let expiryYear: string | undefined

  const flush = () => {
    const name = nameParts.join(' ').replace(/\s+/g, ' ').trim()
    if (!name || name.length < 3) { nameParts = []; location = undefined; completedYear = undefined; expiryYear = undefined; return }
    results.push({
      id: `training-${results.length}-${name}`,
      name,
      location,
      completedDate: completedYear ? `${completedYear}-01-01` : undefined,
      expiryDate: expiryYear ? `${expiryYear}-01-01` : undefined,
    })
    nameParts = []
    location = undefined
    completedYear = undefined
    expiryYear = undefined
  }

  const expandedValues = values.flatMap((value) => value.length > 180
    ? value.split(/(?=(?:Compressed Air|Medicals?\b|Protected Species|Marine Mammal|MSeis\b|Photography Course|Certificate of Proficiency|Protection Equipment|Orca Operator|Work Boat|Radar and ARPA))/i)
    : [value])
  for (const raw of expandedValues) {
    const line = raw.replace(/\s+/g, ' ').trim()
    if (!line || /^N\/A$/i.test(line)) continue

    const completedMatch = line.match(/Completed\s+(\d{4})/i)
    const expiresMatch = line.match(/Expires\s+(\d{4})/i)
    const rawYears = [...line.matchAll(/\b(19|20)\d{2}\b/g)].map((match) => match[0])
    if (rawYears.length > 0) {
      completedYear = completedYear || rawYears[0]
      if (rawYears.length > 1) expiryYear = rawYears[rawYears.length - 1]
      const withoutYears = line.replace(/\b(19|20)\d{2}\b/g, '').replace(/\bN\/A\b/gi, '').trim()
      if (withoutYears) nameParts.push(withoutYears)
      flush()
      continue
    }

    if (completedMatch && !expiresMatch) {
      completedYear = completedMatch[1]
      flush()
      continue
    }
    if (expiresMatch) {
      expiryYear = expiresMatch[1]
      if (!completedYear && completedMatch) completedYear = completedMatch[1]
      flush()
      continue
    }
    if (isStatusLine(line)) {
      flush()
      continue
    }
    if (isLocation(line)) {
      location = line.trim()
      continue
    }
    nameParts.push(line.replace(/[,:-]+$/, '').trim())
  }
  flush()
  return results
}

export function backendCrewToProfile(raw: BackendCrew): UserProfile {
  let tags: string[] = []
  try {
    if (raw.tags) tags = JSON.parse(raw.tags)
    if (!Array.isArray(tags)) tags = []
  } catch {
    tags = []
  }

  const availability = mapAvailability(raw.availabilityStatus)
  const dept = departmentFromTags(tags)
  const location = raw.nationality ? `${raw.nationality}` : 'Location not recorded'
  // Live records provide audited experience from work history. The legacy
  // fallback only applies to older records that have not been calculated yet.
  let years = 0
  if (raw.yearsOfExperience != null) years = raw.yearsOfExperience
  else if (raw.profileCompletenessScore != null) years = 0

  const expertise = tags.filter((tag) => /^(MMO|PAM|ADD|HSE|QC|PSO|Observer)$/i.test(tag.trim()))
  const systemNames = ['PAMGuard', 'ADD', 'ADD Lofitech', 'Microsoft Office Suite', 'QGIS']
  const skills = tags.filter((tag) => !expertise.includes(tag) && !systemNames.some((name) => tag.trim().toLowerCase() === name.toLowerCase()))
  // The real certification names, not a regex guess over free-text tags —
  // a tag like "Experienced in operating PAMGuard software" used to match
  // the old /BOSIET|MMO|PAM|.../ pattern and show up as a fake "certification".
  const displayCerts = (raw.certifications || []).map((cert) => cert.certType)
  const primarySpecialty = tags.find((tag) => /\b(MMO|PAM|HSE|survey|environmental)\b/i.test(tag)) || tags[0]
  let geographicalExperience: string[] = []
  try {
    const parsed = raw.geographicalExperience ? JSON.parse(raw.geographicalExperience) : []
    geographicalExperience = Array.isArray(parsed) ? parsed.filter((value): value is string => typeof value === 'string') : []
  } catch {
    geographicalExperience = []
  }
  let systemsExperience: string[] = []
  try {
    const parsed = raw.systemsExperience ? JSON.parse(raw.systemsExperience) : []
    systemsExperience = Array.isArray(parsed) ? parsed.filter((value): value is string => typeof value === 'string') : []
  } catch {
    systemsExperience = []
  }
  if ((systemsExperience.some((value) => /\bADD\b/i.test(value)) || tags.some((value) => /\bADD\b/i.test(value))) && !expertise.some((value) => value.toUpperCase() === 'ADD')) {
    expertise.push('ADD')
  }
  const systemsCategories = { hardware: [] as string[], software: [] as string[], instrumentation: [] as string[], other: [] as string[] }
  systemsExperience.forEach((value) => {
    if (/camera|binocular|laptop|garmin|gps|thermal imaging/i.test(value)) systemsCategories.instrumentation.push(value)
    else if (/pamguard|software|navigation|positioning system|microsoft|office|linux|qgis/i.test(value)) systemsCategories.software.push(value)
    else if (/equipment|integrated navigation/i.test(value)) systemsCategories.hardware.push(value)
    else systemsCategories.other.push(value)
  })
  let trainingQualifications: string[] = []
  try {
    const parsed = raw.trainingQualifications ? JSON.parse(raw.trainingQualifications) : []
    trainingQualifications = Array.isArray(parsed) ? parsed.filter((value): value is string => typeof value === 'string') : []
  } catch {
    trainingQualifications = []
  }

  return {
    id: raw.id,
    name: raw.fullName,
    title: primarySpecialty ? `${primarySpecialty} Contractor` : 'Contractor',
    avatar: avatarFor(raw.fullName),
    company: 'Company not recorded',
    department: dept,
    location,
    remoteType: 'On-site' as RemoteType,
    yearsOfExperience: years,
    skills,
    expertise,
    // Real CV-derived text when the deterministic extractor found one;
    // the synthesized fallback only covers contractors without a
    // processed CV yet.
    bio:
      raw.professionalSummary ||
      `Consultant ${raw.fullName} — ${dept}. ` +
      (raw.nationality ? `Nationality: ${raw.nationality}. ` : '') +
      `Availability: ${availability}. ` +
      (tags.length ? `Core: ${tags.slice(0, 3).join(', ')}.` : 'No skills recorded.'),
    professionalSummary: raw.professionalSummary || undefined,
    availability,
    education: raw.education || 'Education not recorded',
    nationality: raw.nationality || undefined,
    countryOfResidence: raw.countryOfResidence || undefined,
    dateOfBirth: raw.dateOfBirth || undefined,
    gender: raw.gender || undefined,
    languages: Array.isArray(raw.languages) ? raw.languages : undefined,
    flyingPoint: raw.flyingPoint || undefined,
    geographicalExperience,
    systemsExperience,
    systemsCategories,
    trainingQualifications,
    trainingDetails: normalizeTraining(trainingQualifications),
    certificationDetails: (raw.certifications || []).map((cert) => ({
      id: cert.id,
      name: cert.certType,
      issueDate: cert.issueDate || undefined,
      expiryDate: cert.expiryDate || undefined,
      status: cert.status || undefined,
    })),
    workHistory: (raw.workHistory || []).map((entry) => ({
      id: entry.id,
      clientName: entry.clientName || undefined,
      projectName: entry.projectName || undefined,
      country: entry.country || undefined,
      location: entry.location || undefined,
      projectType: entry.projectType || undefined,
      role: entry.role || undefined,
      responsibilities: entry.responsibilities || undefined,
      startDate: entry.startDate || undefined,
      endDate: entry.endDate || undefined,
      status: entry.status || undefined,
    })),
    email: raw.email || '',
    phone: raw.phone || undefined,
    dayRate: undefined,
    hourlyRate: undefined,
    certifications: displayCerts,
    surveyTypes: [],
    featuredProjects: [],
    pastCompanies: Array.from(
      new Set((raw.workHistory || []).map((entry) => entry.clientName).filter((name): name is string => !!name))
    ),
    rating: undefined,
    reviewCount: undefined,
    isHighlyRecommended: false,
    dateAdded: raw.createdAt ? raw.createdAt.slice(0, 10) : undefined,
    documents: [],
  }
}

export function backendCrewListToProfiles(list: BackendCrew[]): UserProfile[] {
  return list.map(backendCrewToProfile)
}
