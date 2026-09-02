import { FC } from 'react';
import { CheckCircle2, SpellCheck } from 'lucide-react';
import { CrewQueryResult } from '../hooks/useCrewQuery';

interface CrewQuerySummaryProps {
  data: CrewQueryResult | null;
  loading: boolean;
  error: string | null;
  onRemoveCriterion?: (key: string, value?: string) => void;
}

type Criterion = { key: string; label: string; value?: string };

export const CrewQuerySummary: FC<CrewQuerySummaryProps> = ({ data, loading, onRemoveCriterion }) => {

  if (loading) {
    return (
      <div className="mb-4 rounded-[10px] border border-border-subtle/60 bg-surface/40 px-4 py-3 animate-pulse">
        <div className="flex items-center gap-2 text-xs text-muted">
          <span>Understanding your requirements…</span>
        </div>
      </div>
    );
  }

  if (!data || (!data.summary && Object.keys(data.criteria || {}).length === 0)) return null;
  const criteria = data.criteria || {};
  const criteriaLabels = [
    criteria.nationality ? { key: 'nationality', label: `${String(criteria.nationality)} nationality` } : null,
    criteria.medical_valid ? { key: 'medical', label: 'Current medical' } : criteria.medical_required ? { key: 'medical', label: 'Medical record' } : null,
    ...(Array.isArray(criteria.certification_keywords)
      ? criteria.certification_keywords.map((value) => ({ key: 'certification_keywords', value: String(value), label: `${String(value)} qualification` }))
      : []),
    ...(Array.isArray(criteria.certifications)
      ? criteria.certifications
          .filter((value) => !(criteria.medical_required && /medical/i.test(String(value))))
          .map((value) => ({ key: 'certifications', value: String(value), label: String(value) }))
      : []),
    criteria.min_experience_years != null
      ? { key: 'experience', label: criteria.max_experience_years === criteria.min_experience_years
        ? `Exactly ${String(criteria.min_experience_years)} years’ experience`
        : `≥ ${String(criteria.min_experience_years)} years’ experience` }
      : null,
    criteria.max_experience_years != null && criteria.min_experience_years == null
      ? { key: 'experience', label: `≤ ${String(criteria.max_experience_years)} years’ experience` }
      : null,
    criteria.location ? { key: 'location', label: String(criteria.location) } : null,
    criteria.availability ? { key: 'availability', label: `Availability: ${String(criteria.availability).replaceAll('_', ' ')}` } : null,
    criteria.project_type ? { key: 'project_type', label: String(criteria.project_type) } : null,
    ...(Array.isArray(criteria.skills) ? criteria.skills.map((value) => ({ key: 'skills', value: String(value), label: String(value) })) : []),
  ].filter((criterion): criterion is Criterion => Boolean(criterion));
  const corrections = Array.isArray(criteria.corrections)
    ? criteria.corrections.filter(
        (correction): correction is { from: string; to: string } =>
          Boolean(correction)
          && typeof correction === 'object'
          && typeof (correction as { from?: unknown }).from === 'string'
          && typeof (correction as { to?: unknown }).to === 'string'
      )
    : [];

  return (
    <section className="mb-4 rounded-[10px] border border-border-subtle/80 bg-surface/55 px-4 py-3" aria-label="Search interpretation">
      <div className="flex items-start gap-2.5">
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-positive" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          {criteriaLabels.length > 0 && (
            <div>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
                Search criteria · all required {onRemoveCriterion ? '· click a criterion to remove it' : ''}
              </p>
              <div className="flex flex-wrap gap-1.5" aria-label="Applied contractor requirements">
                {criteriaLabels.map((criterion) => (
                  <button
                    key={`${criterion.key}-${criterion.value || criterion.label}`}
                    type="button"
                    disabled={!onRemoveCriterion}
                    onClick={() => onRemoveCriterion?.(criterion.key, criterion.value)}
                    className="rounded-md border border-positive-border/60 bg-positive-soft/30 px-2 py-1 text-xs font-medium text-positive transition-colors enabled:cursor-pointer enabled:hover:border-positive-border enabled:hover:bg-positive-soft/40 disabled:cursor-default"
                    title={onRemoveCriterion ? `Remove ${criterion.label}` : undefined}
                    aria-label={onRemoveCriterion ? `Remove ${criterion.label}` : undefined}
                  >
                    {criterion.label}{onRemoveCriterion ? ' ×' : ''}
                  </button>
                ))}
              </div>
            </div>
          )}
          {corrections.length > 0 && (
            <div className="mt-2.5 flex items-start gap-1.5 rounded-lg border border-warning-border/50 bg-warning-soft/20 px-2.5 py-2 text-xs text-warning/85" aria-live="polite">
              <SpellCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" aria-hidden="true" />
              <span>Corrected spelling: {corrections.map(({ from, to }) => `“${from}” → “${to}”`).join(' · ')}</span>
            </div>
          )}
          {data.summary && <p className="mt-2.5 text-xs font-medium text-secondary">{data.summary}</p>}
        </div>
      </div>
    </section>
  );
};
