import { UserProfile } from '../types';

export interface SkillAxisData {
  axis: string;
  value: number; // 0 to 100
  level: string; // 'Expert' | 'Senior' | 'Proficient' | 'Competent'
  details: string[];
}

export function computeCandidateSkillScores(profile: UserProfile): SkillAxisData[] {
  const combinedText = `${profile.title} ${profile.department} ${profile.bio} ${profile.skills.join(' ')} ${(profile.surveyTypes || []).join(' ')} ${(profile.certifications || []).join(' ')}`.toLowerCase();

  const expMultiplier = Math.min(1.2, 0.7 + (profile.yearsOfExperience || 3) * 0.035);

  // 1. Geotechnical
  const geotechKeywords = ['geotech', 'geotechnical', 'soil', 'core', 'vibrocore', 'cpt', 'borehole', 'laboratory', 'logging', 'sampling', 'benthic', 'sediment'];
  const geotechMatches = geotechKeywords.filter(k => combinedText.includes(k)).length;
  let geotechScore = Math.min(98, Math.round((geotechMatches * 20 + 35) * expMultiplier));
  if (profile.department.toLowerCase().includes('geotech') || profile.title.toLowerCase().includes('geotech')) {
    geotechScore = Math.max(85, geotechScore);
  }

  // 2. Environmental
  const envKeywords = ['environmental', 'mmo', 'pam', 'marine mammal', 'ecology', 'benthic', 'protected species', 'jncc', 'biodiversity', 'esg', 'monitoring', 'passive acoustic'];
  const envMatches = envKeywords.filter(k => combinedText.includes(k)).length;
  let envScore = Math.min(98, Math.round((envMatches * 22 + 30) * expMultiplier));
  if (profile.department.toLowerCase().includes('environmental') || profile.title.toLowerCase().includes('mmo') || profile.title.toLowerCase().includes('environmental')) {
    envScore = Math.max(88, envScore);
  }

  // 3. Data Analysis & Processing
  const dataKeywords = ['data', 'analysis', 'gis', 'python', 'caris', 'qgis', 'matlab', 'processing', 'oasis montaj', 'kingdom', 'arcgis', 'modeling', 'mapping', 'survey report'];
  const dataMatches = dataKeywords.filter(k => combinedText.includes(k)).length;
  let dataScore = Math.min(98, Math.round((dataMatches * 18 + 40) * expMultiplier));
  if (profile.skills.some(s => s.toLowerCase().includes('gis') || s.toLowerCase().includes('data') || s.toLowerCase().includes('caris'))) {
    dataScore = Math.max(82, dataScore);
  }

  // 4. Geophysics & Hydrography
  const geoKeywords = ['geophys', 'hydrograph', 'multibeam', 'sonar', 'side scan', 'sub-bottom', 'magnetometer', 'bathymetry', 'seismic', 'nav', 'positioning', 'eiva'];
  const geoMatches = geoKeywords.filter(k => combinedText.includes(k)).length;
  let geoScore = Math.min(98, Math.round((geoMatches * 19 + 35) * expMultiplier));
  if (profile.department.toLowerCase().includes('geophys') || profile.department.toLowerCase().includes('hydro') || profile.title.toLowerCase().includes('geophys')) {
    geoScore = Math.max(86, geoScore);
  }

  // 5. Offshore Safety & HSE
  const hseKeywords = ['bosiet', 'gwo', 'stcw', 'safety', 'misto', 'ca-ebs', 'offshore', 'risk assessment', 'hse', 'oguk', 'first aid', 'survival'];
  const hseMatches = hseKeywords.filter(k => combinedText.includes(k)).length;
  let hseScore = Math.min(99, Math.round((hseMatches * 18 + 45) * expMultiplier));
  if ((profile.certifications || []).length >= 3) {
    hseScore = Math.max(90, hseScore);
  }

  // 6. QC & Client Representation
  const qcKeywords = ['qc', 'quality control', 'client rep', 'party chief', 'lead', 'reporting', 'management', 'audit', 'senior', 'supervision', 'signoff'];
  const qcMatches = qcKeywords.filter(k => combinedText.includes(k)).length;
  let qcScore = Math.min(98, Math.round((qcMatches * 20 + 35) * expMultiplier));
  if (profile.title.toLowerCase().includes('lead') || profile.title.toLowerCase().includes('chief') || profile.title.toLowerCase().includes('rep') || profile.yearsOfExperience >= 8) {
    qcScore = Math.max(88, qcScore);
  }

  const getLevel = (score: number): string => {
    if (score >= 88) return 'Expert';
    if (score >= 75) return 'Senior';
    if (score >= 60) return 'Proficient';
    return 'Competent';
  };

  return [
    {
      axis: 'Geotechnical',
      value: Math.max(25, Math.min(98, geotechScore)),
      level: getLevel(geotechScore),
      details: profile.skills.filter(s => geotechKeywords.some(k => s.toLowerCase().includes(k))),
    },
    {
      axis: 'Environmental',
      value: Math.max(25, Math.min(98, envScore)),
      level: getLevel(envScore),
      details: profile.skills.filter(s => envKeywords.some(k => s.toLowerCase().includes(k))),
    },
    {
      axis: 'Data Analysis',
      value: Math.max(25, Math.min(98, dataScore)),
      level: getLevel(dataScore),
      details: profile.skills.filter(s => dataKeywords.some(k => s.toLowerCase().includes(k))),
    },
    {
      axis: 'Geophysics',
      value: Math.max(25, Math.min(98, geoScore)),
      level: getLevel(geoScore),
      details: profile.skills.filter(s => geoKeywords.some(k => s.toLowerCase().includes(k))),
    },
    {
      axis: 'Offshore HSE',
      value: Math.max(25, Math.min(98, hseScore)),
      level: getLevel(hseScore),
      details: (profile.certifications || []).slice(0, 3),
    },
    {
      axis: 'QC & Reporting',
      value: Math.max(25, Math.min(98, qcScore)),
      level: getLevel(qcScore),
      details: [`${profile.yearsOfExperience}y Track Record`, profile.isHighlyRecommended ? 'Verified Rep' : 'Field QC'],
    },
  ];
}
