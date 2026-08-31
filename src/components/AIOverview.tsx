import React, { useState } from 'react';
import { Sparkles, TrendingUp, CheckCircle2, Award, ChevronUp, ChevronDown, Zap } from 'lucide-react';
import { AIOverviewData } from '../types';

interface AIOverviewProps {
  data: AIOverviewData | null;
  query: string;
}

export const AIOverview: React.FC<AIOverviewProps> = ({ data, query }) => {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!data) return null;

  return (
    <div
      id="gemini-ai-overview"
      className="relative rounded-3xl bg-gradient-to-br from-indigo-950/40 via-zinc-900/90 to-purple-950/30 border border-indigo-500/30 p-5 sm:p-6 shadow-xl backdrop-blur-xl overflow-hidden transition-all duration-300"
    >
      {/* Subtle Aurora Ambient Glow */}
      <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none -z-10" />

      {/* Header Bar */}
      <div className="flex items-center justify-between gap-3 pb-3 border-b border-indigo-500/20">
        <div className="flex items-center gap-2.5">
          <div className="w-6 h-6 rounded-xl bg-indigo-500/20 border border-indigo-400/40 flex items-center justify-center">
            <Sparkles className="w-3.5 h-3.5 text-indigo-300 animate-pulse" />
          </div>
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-300 flex items-center gap-1.5">
              AI Talent Overview
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-md bg-indigo-500/20 text-indigo-200 border border-indigo-400/30">
                Gemini Synthesis
              </span>
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="p-1 rounded-xl text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors cursor-pointer text-xs flex items-center gap-1"
        >
          <span>{isExpanded ? 'Collapse' : 'Expand'}</span>
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>
      </div>

      {/* Main Content Body */}
      {isExpanded && (
        <div className="pt-4 space-y-4">
          {/* Main Narrative Summary */}
          <p className="text-xs sm:text-sm text-zinc-200 leading-relaxed font-normal">
            {data.summary}
          </p>

          {/* Key Insights & Stats */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-1">
            {data.keyInsights.map((insight, idx) => (
              <div
                key={idx}
                className="p-3 rounded-2xl bg-zinc-950/50 border border-zinc-800/80 flex items-start gap-2.5"
              >
                <CheckCircle2 className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                <span className="text-xs text-zinc-300 font-medium leading-normal">
                  {insight}
                </span>
              </div>
            ))}
          </div>

          {/* Top Skills in Cohort */}
          {data.topSkillsFound.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
              <span className="text-zinc-400 font-semibold flex items-center gap-1 text-[11px]">
                <Zap className="w-3 h-3 text-amber-400" />
                Dominant Skills:
              </span>
              {data.topSkillsFound.map((skill) => (
                <span
                  key={skill}
                  className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-500/15 border border-indigo-500/30 text-indigo-200"
                >
                  {skill}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
