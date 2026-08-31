import React, { useMemo } from 'react';
import { UserProfile } from '../types';
import { SKILL_CATEGORIES } from '../data/mockProfiles';
import { Compass, Anchor, ShieldCheck } from 'lucide-react';

interface SummaryStatsBarProps {
  profiles: UserProfile[];
}

export const SummaryStatsBar: React.FC<SummaryStatsBarProps> = ({ profiles }) => {
  const stats = useMemo(() => {
    if (!profiles.length) {
      return {
        avgExperience: '0',
        availableCount: 0,
        availablePercent: 0,
        topCategory: 'None',
        topCategoryPercent: 0,
      };
    }

    // 1. Average Experience
    const totalExp = profiles.reduce((sum, p) => sum + (p.yearsOfExperience || 0), 0);
    const avgExp = (totalExp / profiles.length).toFixed(1);

    // 2. Available immediately for mobilisation
    const availableCount = profiles.filter((p) => p.availability === 'Available immediately').length;
    const availablePercent = Math.round((availableCount / profiles.length) * 100);

    // 3. Top Discipline Category
    const categoryCounts: Record<string, number> = {};
    SKILL_CATEGORIES.forEach((cat) => {
      categoryCounts[cat.name] = 0;
    });

    profiles.forEach((profile) => {
      const matchedCategories = new Set<string>();
      (profile.skills || []).forEach((skill) => {
        const skillLower = skill.toLowerCase();
        SKILL_CATEGORIES.forEach((cat) => {
          if (
            cat.skills.some(
              (s) => s.toLowerCase() === skillLower || skillLower.includes(s.toLowerCase())
            )
          ) {
            matchedCategories.add(cat.name);
          }
        });
      });

      if (matchedCategories.size > 0) {
        matchedCategories.forEach((catName) => {
          categoryCounts[catName] = (categoryCounts[catName] || 0) + 1;
        });
      } else if (profile.department) {
        categoryCounts[profile.department] = (categoryCounts[profile.department] || 0) + 1;
      }
    });

    let topCategory = 'Marine Environmental';
    let maxCount = -1;

    Object.entries(categoryCounts).forEach(([catName, count]) => {
      if (count > maxCount) {
        maxCount = count;
        topCategory = catName;
      }
    });

    const topCategoryPercent = Math.round((Math.max(maxCount, 0) / profiles.length) * 100);

    return {
      avgExperience: avgExp,
      availableCount,
      availablePercent,
      topCategory: maxCount > 0 ? topCategory : profiles[0]?.department || 'Geophysical QC',
      topCategoryPercent,
    };
  }, [profiles]);

  if (!profiles.length) return null;

  return (
    <div
      id="summary-stats-bar"
      className="w-full grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-0 sm:divide-x sm:divide-slate-800/80 bg-slate-900/70 border border-slate-800/90 rounded-2xl p-3 sm:p-3.5 backdrop-blur-md"
    >
      {/* 1. Average Field Experience */}
      <div className="flex items-center gap-3 px-2 sm:px-4">
        <div className="w-8 h-8 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-center text-cyan-400 shrink-0">
          <Anchor className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <div className="text-[11px] text-slate-500 font-medium">Avg Field Experience</div>
          <div className="text-sm font-semibold text-slate-100 mt-0.5 flex items-baseline gap-1">
            <span>{stats.avgExperience}</span>
            <span className="text-xs font-normal text-slate-400">years offshore</span>
          </div>
        </div>
      </div>

      {/* 2. Rapid Mobilisation Pool */}
      <div className="flex items-center gap-3 px-2 sm:px-4">
        <div className="w-8 h-8 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-center text-emerald-400 shrink-0">
          <ShieldCheck className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <div className="text-[11px] text-slate-500 font-medium">Ready for Mobilisation</div>
          <div className="text-sm font-semibold text-slate-100 mt-0.5 flex items-baseline gap-1.5 truncate">
            <span className="text-emerald-400 font-bold">{stats.availableCount}</span>
            <span className="text-xs font-normal text-slate-400">
              ({stats.availablePercent}% available now)
            </span>
          </div>
        </div>
      </div>

      {/* 3. Top Discipline */}
      <div className="flex items-center gap-3 px-2 sm:px-4">
        <div className="w-8 h-8 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-center text-cyan-400 shrink-0">
          <Compass className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <div className="text-[11px] text-slate-500 font-medium">Lead Discipline</div>
          <div
            className="text-sm font-semibold text-slate-100 mt-0.5 truncate"
            title={stats.topCategory}
          >
            {stats.topCategory}
          </div>
        </div>
      </div>
    </div>
  );
};
