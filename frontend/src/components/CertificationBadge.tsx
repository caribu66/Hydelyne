import { FC, useState } from 'react';
import { ShieldCheck, Info } from 'lucide-react';

interface CertificationBadgeProps {
  certification: string;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

const CERT_INFO_MAP: Record<string, { label: string; org: string; description: string }> = {
  BOSIET: {
    label: 'BOSIET + CA-EBS',
    org: 'OPITO Certified',
    description: 'Basic Offshore Safety Induction & Emergency Training with Compressed Air Emergency Breathing System.',
  },
  OGUK: {
    label: 'OGUK Medical',
    org: 'Offshore Energies UK',
    description: 'Valid offshore medical fitness certification for worldwide deployment.',
  },
  JNCC: {
    label: 'JNCC MMO Accredited',
    org: 'UK Statutory Body',
    description: 'Joint Nature Conservation Committee certified Marine Mammal Observer for seismic & piling.',
  },
  MMO: {
    label: 'JNCC MMO Accredited',
    org: 'UK Statutory Body',
    description: 'Joint Nature Conservation Committee certified Marine Mammal Observer for seismic & piling.',
  },
  PAMGUARD: {
    label: 'PAMGUARD Advanced',
    org: 'Bioacoustics Standard',
    description: 'Certified operator in hydrophone array setup and real-time acoustic signal tracking.',
  },
  PAM: {
    label: 'PAMGUARD Advanced',
    org: 'Bioacoustics Standard',
    description: 'Certified operator in hydrophone array setup and real-time acoustic signal tracking.',
  },
  GWO: {
    label: 'GWO Full Package',
    org: 'Global Wind Organisation',
    description: 'Basic Safety Training including Working at Heights, Sea Survival, and First Aid for Offshore Wind.',
  },
  IMCA: {
    label: 'IMCA Client Rep',
    org: 'Marine Contractors Assoc',
    description: 'Accredited Client Representative for Hydrographic Survey, Positioning, and Geotechnical Operations.',
  },
  IOGP: {
    label: 'IOGP Client Rep',
    org: 'Oil & Gas Producers',
    description: 'Geophysical & Seismic Client Representative adhering to IOGP safety and QA/QC specifications.',
  },
  BOEM: {
    label: 'BOEM / BSEE Certified',
    org: 'US Dept of Interior',
    description: 'Protected Species Observer (PSO) certification for Gulf of Mexico and US Atlantic OCS.',
  },
  STCW: {
    label: 'STCW 95 / 2010',
    org: 'IMO Maritime Standard',
    description: 'Standards of Training, Certification and Watchkeeping for seafarers on survey vessels.',
  },
};

export const CertificationBadge: FC<CertificationBadgeProps> = ({
  certification,
  className = '',
  size = 'md',
}) => {
  const [showTooltip, setShowTooltip] = useState(false);

  const matchKey = Object.keys(CERT_INFO_MAP).find((key) =>
    certification.toUpperCase().includes(key)
  );
  const info = matchKey ? CERT_INFO_MAP[matchKey] : null;
  const tooltipId = `cert-tooltip-${certification.replace(/[^a-z0-9]+/gi, '-').toLowerCase()}`;

  return (
    <button
      type="button"
      className="relative inline-flex items-center"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      onFocus={() => setShowTooltip(true)}
      onBlur={() => setShowTooltip(false)}
      onClick={() => info && setShowTooltip((visible) => !visible)}
      aria-expanded={showTooltip}
      aria-describedby={showTooltip && info ? tooltipId : undefined}
      aria-label={`${certification}${info ? `: ${info.description}` : ''}`}
    >
      <span
        className={`inline-flex items-center gap-1 font-mono font-medium rounded-lg border transition-colors cursor-help select-none ${
          size === 'sm'
            ? 'px-1.5 py-0.5 text-xs'
            : size === 'lg' ? 'px-3 py-1.5 text-xs' : 'px-2 py-1 text-xs'
        } ${
          matchKey
            ? 'badge-neutral hover:brightness-95'
            : 'badge-neutral opacity-80 hover:opacity-100'
        } ${className}`}
      >
        <ShieldCheck className={size === 'sm' ? 'w-2.5 h-2.5 shrink-0' : size === 'lg' ? 'w-3.5 h-3.5 shrink-0' : 'w-3 h-3 shrink-0'} />
        <span className="truncate max-w-[170px]">{certification}</span>
        {info && <Info className="w-2.5 h-2.5 ml-0.5 shrink-0 opacity-75" />}
      </span>

      {showTooltip && info && (
        <div id={tooltipId} role="tooltip" className="absolute z-[100] top-full left-1/2 -translate-x-1/2 mt-2 w-64 p-2.5 rounded-[10px] bg-surface border border-border-strong text-xs text-primary shadow-xl pointer-events-none transition-all">
          <div className="flex items-center justify-between gap-1 mb-1 border-b border-border-subtle pb-1">
            <span className="font-semibold text-accent font-mono text-xs">{info.label}</span>
            <span className="text-xs text-secondary">{info.org}</span>
          </div>
          <p className="text-xs text-secondary leading-snug">{info.description}</p>
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 -mb-px border-4 border-transparent border-b-zinc-800" />
        </div>
      )}
    </button>
  );
};
