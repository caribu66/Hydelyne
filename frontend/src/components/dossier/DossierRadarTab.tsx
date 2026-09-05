import { FC } from 'react';
import { UserProfile } from '../../types';
import { CandidateSkillRadarChart } from '../CandidateSkillRadarChart';

interface DossierRadarTabProps {
  profile: UserProfile;
  isFocusMode: boolean;
}

export const DossierRadarTab: FC<DossierRadarTabProps> = ({ profile, isFocusMode }) => {
  return (
    <div className="space-y-4">
      <CandidateSkillRadarChart
        profile={profile}
        size={isFocusMode ? 'lg' : 'md'}
        showLegend={true}
      />
      <div className="bg-canvas/50 p-4 rounded-[10px] border border-border-subtle/70 text-xs text-secondary space-y-1.5">
        <span className="font-semibold text-primary block font-mono text-xs uppercase">
          Methodology & Assessment Criteria
        </span>
        <p>
          Calculated dynamically from verified offshore track records, certifications (BOSIET, GWO,
          STCW), and technical proficiencies in{' '}
          <strong className="text-secondary">Geotechnical</strong>,{' '}
          <strong className="text-secondary">Environmental</strong>, and{' '}
          <strong className="text-secondary">Data Analysis</strong>.
        </p>
      </div>
    </div>
  );
};
