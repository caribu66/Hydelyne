import { FC } from 'react';
import { UserProfile } from '../../types';
import { HighlightText } from '../HighlightText';
import { DossierCollection } from '../DossierCollection';
import { formatExperience } from '../../utils/experience';

interface DossierExperienceTabProps {
  profile: UserProfile;
  searchQuery?: string;
}

export const DossierExperienceTab: FC<DossierExperienceTabProps> = ({
  profile,
  searchQuery = '',
}) => {
  return (
    <div className="space-y-4">
      <section className="space-y-2">
        <h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">
          Track Record & Clients
        </h3>
        <p className="text-secondary leading-relaxed">
          {formatExperience(profile.yearsOfExperience)} years of offshore experience.
        </p>
        {profile.pastCompanies && profile.pastCompanies.length > 0 && (
          <DossierCollection
            items={profile.pastCompanies}
            itemLabel="clients"
            initialItems={8}
            renderItems={(companies) => (
              <div className="flex flex-wrap gap-2">
                {companies.map((company) => (
                  <span
                    key={company}
                    className="px-3 py-1.5 rounded-[10px] bg-surface border border-border-subtle text-secondary"
                  >
                    {company}
                  </span>
                ))}
              </div>
            )}
          />
        )}
      </section>

      {profile.workHistory && profile.workHistory.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">
            Recent Projects
          </h3>
          <DossierCollection
            items={profile.workHistory}
            itemLabel="projects"
            renderItems={(projects) => (
              <div className="overflow-x-auto rounded-[10px] border border-border-subtle">
                <table className="min-w-full text-sm">
                  <thead className="bg-canvas/60 text-xs font-semibold text-secondary uppercase tracking-wider">
                    <tr>
                      <th className="px-3 py-2 text-left">Year</th>
                      <th className="px-3 py-2 text-left">Client</th>
                      <th className="px-3 py-2 text-left">Country</th>
                      <th className="px-3 py-2 text-left">Survey Type</th>
                      <th className="px-3 py-2 text-left">Position</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border-subtle">
                    {projects.map((row, index) => (
                      <tr
                        key={row.id ?? `${row.clientName ?? 'project'}-${index}`}
                        className="text-primary"
                      >
                        <td className="px-3 py-2 whitespace-nowrap">
                          {row.startDate ? row.startDate.slice(0, 4) : ''}
                        </td>
                        <td className="px-3 py-2">{row.clientName}</td>
                        <td className="px-3 py-2">{row.country}</td>
                        <td className="px-3 py-2">{row.projectType}</td>
                        <td className="px-3 py-2">{row.role}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          />
        </section>
      )}

      {profile.geographicalExperience && profile.geographicalExperience.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">
            Geographical Experience
          </h3>
          <DossierCollection
            items={profile.geographicalExperience}
            itemLabel="locations"
            initialItems={8}
            renderItems={(locations) => (
              <div className="flex flex-wrap gap-2">
                {locations.map((place) => (
                  <span
                    key={place}
                    className="px-3 py-1.5 rounded-[10px] bg-surface border border-border-subtle text-secondary"
                  >
                    <HighlightText text={place} query={searchQuery} />
                  </span>
                ))}
              </div>
            )}
          />
        </section>
      )}

      {profile.surveyTypes && profile.surveyTypes.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono">
            Survey Focus
          </h3>
          <DossierCollection
            items={profile.surveyTypes}
            itemLabel="survey disciplines"
            initialItems={8}
            renderItems={(surveyTypes) => (
              <div className="flex flex-wrap gap-2">
                {surveyTypes.map((type) => (
                  <span
                    key={type}
                    className="px-3 py-1.5 rounded-[10px] bg-surface border border-border-subtle text-secondary"
                  >
                    {type}
                  </span>
                ))}
              </div>
            )}
          />
        </section>
      )}
    </div>
  );
};
