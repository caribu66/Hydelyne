import React, { useMemo, useState } from 'react';
import * as d3 from 'd3';
import { UserProfile } from '../types';
import { computeCandidateSkillScores, SkillAxisData } from '../utils/skillRadarUtils';
import { Activity, Info, Award } from 'lucide-react';

interface CandidateSkillRadarChartProps {
  profile: UserProfile;
  size?: 'sm' | 'md' | 'lg';
  showLegend?: boolean;
}

export const CandidateSkillRadarChart: React.FC<CandidateSkillRadarChartProps> = ({
  profile,
  size = 'md',
  showLegend = true,
}) => {
  const [hoveredAxis, setHoveredAxis] = useState<SkillAxisData | null>(null);

  const radarData = useMemo(() => computeCandidateSkillScores(profile), [profile]);

  // Dimension calculations
  const dimensions = useMemo(() => {
    switch (size) {
      case 'sm':
        return { width: 280, height: 260, radius: 85, margin: 40 };
      case 'lg':
        return { width: 440, height: 380, radius: 135, margin: 55 };
      case 'md':
      default:
        return { width: 340, height: 310, radius: 110, margin: 45 };
    }
  }, [size]);

  const { width, height, radius } = dimensions;
  const centerX = width / 2;
  const centerY = height / 2;

  // D3 Scales & Math
  const totalAxes = radarData.length;
  const angleSlice = (Math.PI * 2) / totalAxes;

  // Radial scale: 0 to 100 mapped to 0 to radius
  const rScale = useMemo(() => {
    return d3.scaleLinear().domain([0, 100]).range([0, radius]);
  }, [radius]);

  // Concentric levels (20%, 40%, 60%, 80%, 100%)
  const levels = [20, 40, 60, 80, 100];

  // Calculate polygon points for candidate data
  const polygonPoints = useMemo(() => {
    return radarData.map((d, i) => {
      const angle = angleSlice * i - Math.PI / 2;
      const r = rScale(d.value);
      const x = centerX + r * Math.cos(angle);
      const y = centerY + r * Math.sin(angle);
      return { x, y, data: d, angle };
    });
  }, [radarData, angleSlice, rScale, centerX, centerY]);

  // SVG path generator string for the polygon
  const pathD = useMemo(() => {
    const lineGenerator = d3
      .line<{ x: number; y: number }>()
      .x((d) => d.x)
      .y((d) => d.y)
      .curve(d3.curveLinearClosed);
    return lineGenerator(polygonPoints) || '';
  }, [polygonPoints]);

  // Average score
  const avgScore = useMemo(() => {
    const sum = radarData.reduce((acc, curr) => acc + curr.value, 0);
    return Math.round(sum / radarData.length);
  }, [radarData]);

  return (
    <div className="bg-zinc-950/70 border border-zinc-800/90 rounded-2xl p-4 sm:p-5 flex flex-col items-center relative overflow-hidden shadow-inner">
      {/* Header */}
      <div className="w-full flex items-center justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-zinc-900 border border-zinc-800 flex items-center justify-center text-zinc-300">
            <Activity className="w-3.5 h-3.5" />
          </div>
          <div>
            <h4 className="text-xs font-semibold text-zinc-200 tracking-tight flex items-center gap-1.5 font-mono">
              <span>Competency Radar Analysis</span>
            </h4>
            <p className="text-[10px] text-zinc-500">
              Evaluated across {radarData.length} core offshore disciplines
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-zinc-900 border border-zinc-800 text-zinc-200 text-xs font-mono font-medium">
          <Award className="w-3.5 h-3.5 text-zinc-400" />
          <span>{avgScore}% Composite</span>
        </div>
      </div>

      {/* SVG D3 Chart */}
      <div className="relative flex items-center justify-center my-1">
        <svg
          width={width}
          height={height}
          className="overflow-visible select-none transition-all duration-300"
          viewBox={`0 0 ${width} ${height}`}
        >
          <defs>
            {/* Enterprise Solid Gradient for radar polygon */}
            <linearGradient id={`radarGrad-${profile.id}`} x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#2563eb" stopOpacity="0.30" />
              <stop offset="100%" stopColor="#1e40af" stopOpacity="0.15" />
            </linearGradient>
          </defs>

          {/* Grid Concentric Polygons */}
          {levels.map((level) => {
            const levelRadius = rScale(level);
            const levelPoints = radarData.map((_, i) => {
              const angle = angleSlice * i - Math.PI / 2;
              const x = centerX + levelRadius * Math.cos(angle);
              const y = centerY + levelRadius * Math.sin(angle);
              return `${x},${y}`;
            });

            return (
              <g key={`level-${level}`}>
                <polygon
                  points={levelPoints.join(' ')}
                  className="stroke-zinc-800/80 fill-zinc-900/10"
                  strokeWidth="1"
                  strokeDasharray={level === 100 ? 'none' : '3 3'}
                />
                {/* Level Percentage Label on top axis */}
                <text
                  x={centerX + 4}
                  y={centerY - levelRadius + 3}
                  className="fill-zinc-600 font-mono text-[8px] font-semibold"
                >
                  {level}%
                </text>
              </g>
            );
          })}

          {/* Axis Radial Lines & Text Labels */}
          {radarData.map((d, i) => {
            const angle = angleSlice * i - Math.PI / 2;
            const lineX = centerX + radius * Math.cos(angle);
            const lineY = centerY + radius * Math.sin(angle);

            // Label positioning with offset
            const labelRadius = radius + 22;
            const labelX = centerX + labelRadius * Math.cos(angle);
            const labelY = centerY + labelRadius * Math.sin(angle);

            const isHovered = hoveredAxis?.axis === d.axis;

            // Anchor alignment based on position
            let textAnchor: 'middle' | 'start' | 'end' = 'middle';
            if (Math.cos(angle) > 0.3) textAnchor = 'start';
            else if (Math.cos(angle) < -0.3) textAnchor = 'end';

            return (
              <g
                key={`axis-${d.axis}`}
                className="cursor-pointer group"
                onMouseEnter={() => setHoveredAxis(d)}
                onMouseLeave={() => setHoveredAxis(null)}
              >
                {/* Spoke Line */}
                <line
                  x1={centerX}
                  y1={centerY}
                  x2={lineX}
                  y2={lineY}
                  className={`transition-colors duration-200 ${
                    isHovered ? 'stroke-blue-400 stroke-[1.5]' : 'stroke-zinc-800/90'
                  }`}
                  strokeWidth="1"
                />

                {/* Axis Name Label */}
                <text
                  x={labelX}
                  y={labelY + 4}
                  textAnchor={textAnchor}
                  className={`font-mono text-[10px] font-medium transition-all duration-200 ${
                    isHovered
                      ? 'fill-zinc-100 font-semibold'
                      : d.value >= 80
                      ? 'fill-zinc-300'
                      : 'fill-zinc-500'
                  }`}
                >
                  {d.axis}
                </text>
              </g>
            );
          })}

          {/* Data Radar Polygon */}
          <path
            d={pathD}
            fill={`url(#radarGrad-${profile.id})`}
            stroke="#3b82f6"
            strokeWidth="1.5"
            className="transition-all duration-200 ease-out"
          />

          {/* Point Markers with Hover Rings */}
          {polygonPoints.map(({ x, y, data }, idx) => {
            const isHovered = hoveredAxis?.axis === data.axis;

            return (
              <g
                key={`point-${idx}`}
                className="cursor-pointer transition-transform"
                onMouseEnter={() => setHoveredAxis(data)}
                onMouseLeave={() => setHoveredAxis(null)}
              >
                {/* Outer halo */}
                <circle
                  cx={x}
                  cy={y}
                  r={isHovered ? 6 : 3}
                  className={`transition-all duration-200 ${
                    isHovered
                      ? 'fill-blue-500/20 stroke-blue-400 stroke-1'
                      : 'fill-blue-500/10'
                  }`}
                />
                {/* Inner point */}
                <circle
                  cx={x}
                  cy={y}
                  r={isHovered ? 3.5 : 2}
                  className="fill-zinc-100 stroke-blue-600 stroke-[1]"
                />
              </g>
            );
          })}
        </svg>

        {/* Hovered Axis Tooltip overlay */}
        {hoveredAxis && (
          <div className="absolute top-2 right-2 bg-zinc-900 border border-zinc-700/80 shadow-xl rounded-xl p-2.5 max-w-[200px] pointer-events-none text-left backdrop-blur-md z-10 transition-all">
            <div className="flex items-center justify-between gap-2 border-b border-zinc-800 pb-1 mb-1.5">
              <span className="font-semibold text-xs text-zinc-100">{hoveredAxis.axis}</span>
              <span className="font-mono text-xs font-semibold text-zinc-200">{hoveredAxis.value}%</span>
            </div>
            <div className="flex items-center gap-1 mb-1">
              <span className="text-[10px] text-zinc-400">Rating:</span>
              <span className="text-[10px] font-medium text-zinc-300 uppercase tracking-wide">
                {hoveredAxis.level}
              </span>
            </div>
            {hoveredAxis.details && hoveredAxis.details.length > 0 && (
              <div className="text-[9px] text-zinc-400 flex flex-wrap gap-1 mt-1">
                {hoveredAxis.details.map((item, i) => (
                  <span key={i} className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300">
                    {item}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Axis Breakdown Pills */}
      {showLegend && (
        <div className="w-full grid grid-cols-2 sm:grid-cols-3 gap-1.5 mt-2 pt-2 border-t border-zinc-800/80">
          {radarData.map((d) => {
            const isHovered = hoveredAxis?.axis === d.axis;
            return (
              <div
                key={d.axis}
                onMouseEnter={() => setHoveredAxis(d)}
                onMouseLeave={() => setHoveredAxis(null)}
                className={`p-1.5 rounded-lg border transition-all cursor-pointer flex items-center justify-between gap-1.5 ${
                  isHovered
                    ? 'bg-zinc-800/80 border-zinc-700 text-zinc-100'
                    : 'bg-zinc-900/40 hover:bg-zinc-900 border-zinc-800/60 text-zinc-400'
                }`}
              >
                <div className="min-w-0">
                  <span className="text-[11px] font-medium block truncate">{d.axis}</span>
                  <span className="text-[9px] text-zinc-500 font-mono">{d.level}</span>
                </div>
                <span className="font-mono text-xs font-semibold text-zinc-300 shrink-0">
                  {d.value}%
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Footer hint */}
      <div className="w-full flex items-center justify-between text-[10px] text-zinc-500 mt-2.5 pt-1.5 border-t border-zinc-900">
        <span className="flex items-center gap-1">
          <Info className="w-3 h-3 text-zinc-500" />
          <span>Vector Radar Analytics</span>
        </span>
        <span className="font-mono text-zinc-500">Hydenlyne Standard</span>
      </div>
    </div>
  );
};
