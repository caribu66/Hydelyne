import { FC } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { UserProfile } from '../types';
import { formatExperience } from '../utils/experience';

interface MatchEvidenceProps {
  profile: UserProfile;
  criteria?: Record<string, unknown>;
  resultCertifications?: string[];
  compact?: boolean;
}

/** A concise, factual explanation of why this result met the active brief. */
export const MatchEvidence: FC<MatchEvidenceProps> = ({
  profile,
  criteria,
  resultCertifications = [],
  compact = false,
}) => {
  if (!criteria || Object.keys(criteria).length === 0) return null;

  const evidence: string[] = [];
  const knownCertifications = [
    ...(profile.certifications || []),
    ...resultCertifications,
  ];
  if (criteria.nationality) evidence.push(`${String(criteria.nationality)} nationality`);
  if (criteria.medical_valid) evidence.push('Current medical');
  else if (criteria.medical_required) evidence.push('Medical record');

  if (Array.isArray(criteria.certification_keywords)) {
    criteria.certification_keywords.forEach((value) => {
      const requested = String(value);
      const exactMatch = knownCertifications.find((certification) =>
        certification.toLowerCase().includes(requested.toLowerCase())
      );
      evidence.push(exactMatch || `${requested} qualification`);
    });
  }
  if (Array.isArray(criteria.certifications)) {
    criteria.certifications
      .filter((value) => !(criteria.medical_required && /medical/i.test(String(value))))
      .forEach((value) => {
        const requested = String(value);
        const exactMatch = knownCertifications.find((certification) =>
          certification.toLowerCase().includes(requested.toLowerCase())
        );
        evidence.push(exactMatch || requested);
      });
  }
  if (criteria.min_experience_years != null) evidence.push(`${formatExperience(profile.yearsOfExperience)} years’ experience`);
  if (criteria.location) evidence.push(String(criteria.location));
  if (criteria.availability) evidence.push('Availability confirmed');
  if (criteria.project_type) evidence.push(String(criteria.project_type));
  if (Array.isArray(criteria.skills)) criteria.skills.forEach((value) => evidence.push(String(value)));

  const uniqueEvidence = [...new Set(evidence)].slice(0, compact ? 2 : 4);
  if (uniqueEvidence.length === 0) return null;

  return (
    <div className={compact ? 'mt-1.5 flex items-start gap-1.5 text-xs leading-4 text-positive/85' : 'rounded-lg border border-positive-border/45 bg-positive-soft/20 px-2.5 py-2'}>
      <CheckCircle2 className={compact ? 'mt-0.5 h-3 w-3 shrink-0 text-positive' : 'mt-0.5 h-3.5 w-3.5 shrink-0 text-positive'} aria-hidden="true" />
      <div className="min-w-0">
        {!compact && <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-positive/75">Why matched</p>}
        <p className={compact ? 'truncate' : 'text-xs leading-5 text-positive/90'}>
          {uniqueEvidence.join(' · ')}
        </p>
      </div>
    </div>
  );
};
