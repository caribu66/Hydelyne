import { FC } from 'react';
import { UserProfile } from '../../types';
import { HighlightText } from '../HighlightText';
import { DossierCollection } from '../DossierCollection';

interface DossierExpertiseTabProps {
  profile: UserProfile;
  skillsQuery: string;
  onSkillsQueryChange: (query: string) => void;
}

export const DossierExpertiseTab: FC<DossierExpertiseTabProps> = ({
  profile,
  skillsQuery,
  onSkillsQueryChange,
}) => {
  const profileSkills = Array.from(new Set([...(profile.skills ?? []), ...(profile.expertise ?? [])]));
  const normalizedSkillsQuery = skillsQuery.trim().toLocaleLowerCase();
  const matchingSkills = normalizedSkillsQuery
    ? profileSkills.filter((skill) => skill.toLocaleLowerCase().includes(normalizedSkillsQuery))
    : profileSkills;

  return (
    <div className="space-y-4">
      <section className="space-y-3" aria-labelledby="skills-heading">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h3
              id="skills-heading"
              className="text-xs font-semibold uppercase tracking-wider text-secondary font-mono"
            >
              Skills & technical competencies
            </h3>
            <p className="mt-1 text-sm text-secondary">
              {matchingSkills.length} of {profileSkills.length} skills shown
            </p>
          </div>
          <label className="block sm:w-72">
            <span className="sr-only">Find a skill in {profile.name}'s profile</span>
            <input
              type="search"
              value={skillsQuery}
              onChange={(event) => onSkillsQueryChange(event.target.value)}
              placeholder="Find a skill, tool, or competency"
              className="min-h-11 w-full rounded-[10px] border border-border-strong bg-canvas px-3 text-sm text-primary placeholder:text-muted focus:outline-hidden focus:ring-2 focus:ring-focus"
            />
          </label>
        </div>

        {matchingSkills.length > 0 ? (
          <DossierCollection
            items={matchingSkills}
            itemLabel="skills"
            initialItems={normalizedSkillsQuery ? matchingSkills.length : 8}
            renderItems={(skills) => (
              <ul className="grid grid-cols-1 gap-2 lg:grid-cols-2">
                {skills.map((skill) => (
                  <li
                    key={skill}
                    className="flex min-h-11 items-start gap-2 rounded-[10px] border border-border-subtle bg-canvas/60 px-3 py-2 text-sm leading-5 text-secondary"
                  >
                    <span
                      className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent"
                      aria-hidden="true"
                    />
                    <HighlightText text={skill} query={skillsQuery} />
                  </li>
                ))}
              </ul>
            )}
          />
        ) : (
          <div className="rounded-[10px] border border-border-subtle bg-canvas/60 px-3 py-4 text-sm text-secondary">
            No skills match “{skillsQuery}”.
          </div>
        )}
      </section>
    </div>
  );
};
