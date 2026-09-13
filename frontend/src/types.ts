export type RemoteType = 'Remote' | 'Hybrid' | 'On-site';
export type AvailabilityStatus = 'Available immediately' | 'Open to offers' | 'Employed (Not looking)' | 'Contract / Freelance' | 'Unavailable';

export interface WorkExperience {
  company: string;
  role: string;
  duration: string;
  description: string;
}

export type DocumentCategory =
  | 'cv'
  | 'certificate'
  | 'medical'
  | 'seamans_book'
  | 'survey_report'
  | 'other';

export interface SpecialistDocument {
  id: string;
  title: string;
  category: DocumentCategory;
  fileName: string;
  fileSize?: string;
  fileUrl?: string; // Data URL or external link
  issueDate?: string;
  expiryDate?: string;
  isVerified?: boolean;
  uploadedAt: string;
  notes?: string;
  extractionStatus?: string;
  extractedText?: string;
  extractedData?: Record<string, unknown>;
  extractionConfidence?: Record<string, unknown>;
}

export interface UserProfile {
  id: string;
  name: string;
  title: string;
  avatar: string;
  company: string;
  department: string;
  location: string;
  remoteType: RemoteType;
  yearsOfExperience: number | null;
  skills: string[];
  expertise?: string[];
  bio: string;
  professionalSummary?: string;
  availability: AvailabilityStatus;
  availabilityDate?: string;
  education: string;
  nationality?: string;
  countryOfResidence?: string;
  dateOfBirth?: string;
  gender?: string;
  languages?: string[];
  flyingPoint?: string;
  geographicalExperience?: string[];
  systemsExperience?: string[];
  systemsCategories?: { hardware: string[]; software: string[]; instrumentation: string[]; other: string[] };
  trainingQualifications?: string[];
  trainingDetails?: Array<{ id: string; name: string; location?: string; completedDate?: string; expiryDate?: string }>;
  certificationDetails?: Array<{
    id: string;
    name: string;
    issueDate?: string;
    expiryDate?: string;
    status?: string;
    verificationStatus?: string;
    documentRef?: string;
    certNumber?: string;
    issuingBody?: string;
  }>;
  email: string;
  phone?: string;
  linkedinUrl?: string;
  hourlyRate?: number;
  featuredProjects?: string[];
  pastCompanies?: string[];
  certifications?: string[];
  workHistory?: Array<{
    id?: string;
    year?: string | null;
    clientName?: string | null;
    projectName?: string | null;
    country?: string | null;
    location?: string | null;
    projectType?: string | null;
    role?: string | null;
    responsibilities?: string | null;
    startDate?: string | null;
    endDate?: string | null;
    status?: string | null;
  }>;
  surveyTypes?: string[];
  dayRate?: number;
  rating?: number;
  reviewCount?: number;
  isHighlyRecommended?: boolean;
  dateAdded?: string;
  documents?: SpecialistDocument[];
  medical?: { status?: string; expiry?: string; provider?: string };
}

export type SortOption =
  | 'relevance'
  | 'experience-desc'
  | 'recent'
  | 'experience-asc'
  | 'name-asc'
  | 'name-desc'
  | 'rate-desc'
  | 'rate-asc'
  | 'rating-desc';

export interface FilterState {
  keyword: string;
  locations: string[];
  remoteTypes: RemoteType[];
  selectedSkills: string[];
  skillMatchMode: 'ANY' | 'ALL';
  minExperience: number;
  maxExperience: number;
  companies: string[];
  availability: AvailabilityStatus[];
  departments: string[];
  sortBy: SortOption;
}

export interface AIOverviewData {
  summary: string;
  keyInsights: string[];
  topSkillsFound: string[];
  avgExperience: number | null;
  availablePercentage: number;
  highlightProfileId?: string;
}

export interface FilterPreset {
  id: string;
  name: string;
  description: string;
  query?: string;
  filters: Partial<FilterState>;
}

export type DossierTab = 'dossier' | 'experience' | 'expertise' | 'systems' | 'credentials' | 'radar' | 'vault';

export type CampaignAssignmentStatus = 'proposed' | 'confirmed' | 'on_board' | 'completed' | 'cancelled';

export interface CampaignAssignment {
  id: string;
  crewMemberId: string;
  projectId?: string | null;
  vesselImo: string;
  roleOnBoard: string;
  startDate: string;
  endDate: string;
  status: CampaignAssignmentStatus;
  agreedDayRate?: number | null;
  notes?: string | null;
  createdAt: string;
  updatedAt: string;
  crewName?: string | null;
  vesselName?: string | null;
  projectName?: string | null;
}
