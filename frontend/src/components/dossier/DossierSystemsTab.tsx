import { FC } from 'react';
import { UserProfile } from '../../types';
import { DossierCollection } from '../DossierCollection';

interface DossierSystemsTabProps {
  profile: UserProfile;
}

export const DossierSystemsTab: FC<DossierSystemsTabProps> = ({ profile }) => {
  const hasSystemsCategories = Boolean(
    profile.systemsCategories &&
      Object.values(profile.systemsCategories).some((items) => items.length > 0),
  );

  return (
    <div className="space-y-4">
      {hasSystemsCategories && profile.systemsCategories ? (
        (Object.entries(profile.systemsCategories) as [string, string[]][]).map(
          ([category, items]) =>
            items.length > 0 && (
              <section key={category} className="space-y-2">
                <h3 className="text-xs font-semibold text-secondary uppercase tracking-wider font-mono capitalize">
                  {category}
                </h3>
                <DossierCollection
                  items={items}
                  itemLabel="systems"
                  initialItems={8}
                  renderItems={(systems) => (
                    <div className="flex flex-wrap gap-2">
                      {systems.map((system) => (
                        <span
                          key={system}
                          className="px-3 py-1.5 rounded-[10px] bg-surface border border-border-subtle text-secondary font-medium text-xs"
                        >
                          {system}
                        </span>
                      ))}
                    </div>
                  )}
                />
              </section>
            ),
        )
      ) : (
        <p className="text-muted">No systems experience was found in the CV.</p>
      )}
    </div>
  );
};
