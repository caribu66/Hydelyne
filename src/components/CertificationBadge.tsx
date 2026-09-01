import React, { useState } from 'react';
import { ShieldCheck, Info } from 'lucide-react';

interface CertificationBadgeProps {
  certification: string;
  className?: string;
  size?: 'sm' | 'md';
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
  PAMGUARD: {
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

export const CertificationBadge: React.FC<CertificationBadgeProps> = ({
  certification,
  className = '',
  size = 'md',
}) => {
  const [showTooltip, setShowTooltip] = useState(false);

  // Match key from cert text
  const matchKey = Object.keys(CERT_INFO_MAP).find((key) =>
    certification.toUpperCase().includes(key)
  );
  const info = matchKey ? CERT_INFO_MAP[matchKey] : null;

  return (
    <div
      className="relative inline-flex items-center"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      onFocus={() => setShowTooltip(true)}
      onBlur={() => setShowTooltip(false)}
      tabIndex={0}
      role="note"
      aria-label={`${certification}${info ? `: ${info.description}` : ''}`}
    >
      <span
        className={`inline-flex items-center gap-1 font-mono font-medium rounded-lg border transition-colors cursor-help select-none ${
          size === 'sm'
            ? 'px-1.5 py-0.5 text-[10px]'
            : 'px-2 py-1 text-[11px]'
        } ${
          matchKey
            ? 'bg-zinc-900 border-zinc-700/80 text-zinc-200 hover:border-zinc-500'
            : 'bg-zinc-900/60 border-zinc-800 text-zinc-400 hover:border-zinc-700'
        } ${className}`}
      >
        <ShieldCheck className={size === 'sm' ? 'w-2.5 h-2.5 text-zinc-400 shrink-0' : 'w-3 h-3 text-zinc-400 shrink-0'} />
        <span className="truncate max-w-[170px]">{certification}</span>
        {info && <Info className="w-2.5 h-2.5 text-zinc-500 ml-0.5 shrink-0" />}
      </span>

      {showTooltip && info && (
        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-2.5 rounded-xl bg-zinc-900 border border-zinc-750 text-xs text-zinc-200 shadow-xl pointer-events-none transition-all">
          <div className="flex items-center justify-between gap-1 mb-1 border-b border-zinc-800 pb-1">
            <span className="font-semibold text-blue-300 font-mono text-[11px]">{info.label}</span>
            <span className="text-[10px] text-zinc-400">{info.org}</span>
          </div>
          <p className="text-[11px] text-zinc-300 leading-snug">{info.description}</p>
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-4 border-transparent border-t-zinc-800" />
        </div>
      )}
    </div>
  );
};
