export type RemoteType = 'Remote' | 'Hybrid' | 'On-site';
export type AvailabilityStatus = 'Available immediately' | 'Open to offers' | 'Employed (Not looking)' | 'Contract / Freelance';

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
  yearsOfExperience: number;
  skills: string[];
  bio: string;
  availability: AvailabilityStatus;
  education: string;
  email: string;
  phone?: string;
  linkedinUrl?: string;
  hourlyRate?: number;
  featuredProjects?: string[];
  pastCompanies?: string[];
  certifications?: string[];
  surveyTypes?: string[];
  dayRate?: number;
  rating?: number;
  reviewCount?: number;
  isHighlyRecommended?: boolean;
  dateAdded?: string;
  documents?: SpecialistDocument[];
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
  avgExperience: number;
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
