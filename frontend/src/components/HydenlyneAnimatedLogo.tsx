import { FC, useState, useEffect } from 'react';
import { motion, useReducedMotion } from 'motion/react';
import { useTheme } from '../hooks/useTheme';
import hydenlyneTextColour from '../assets/hydenlyne-text-colour.png';
import hydenlyneTextWhite from '../assets/hydenlyne-text-white.png';

interface HydenlyneAnimatedLogoProps {
  isFocused?: boolean;
  className?: string;
}

export const HydenlyneAnimatedLogo: FC<HydenlyneAnimatedLogoProps> = ({
  isFocused = false,
  className = '',
}) => {
  const { isDark } = useTheme();
  const prefersReducedMotion = useReducedMotion();
  const [animationComplete, setAnimationComplete] = useState(false);

  useEffect(() => {
    if (prefersReducedMotion) {
      setAnimationComplete(true);
      return undefined;
    }
    const timer = setTimeout(() => {
      setAnimationComplete(true);
    }, 1400);
    return () => {
      clearTimeout(timer);
    };
  }, [prefersReducedMotion]);

  // Exact centerline coordinates matching official Hydenlyne logo geometry
  const pathD = 'M 2 72 L 25 72 L 50 7 L 80 101 L 92 72 L 407 72';

  return (
    <div
      className={`relative select-none ${className}`}
      style={{ width: '180px', height: '48.4px' }}
      aria-label="Hydenlyne"
      role="img"
    >
      {/* Crisp Typography Layer */}
      <img
        src={isDark ? hydenlyneTextWhite : hydenlyneTextColour}
        alt=""
        aria-hidden="true"
        className="absolute inset-0 w-full h-full object-contain pointer-events-none"
      />

      {/* Animated Vector Waveform Layer */}
      <svg
        viewBox="0 0 409 110"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="absolute inset-0 w-full h-full overflow-visible pointer-events-none"
        aria-hidden="true"
      >
        {/* Static Base Line (shown after sweep or under reduced motion) */}
        {(animationComplete || prefersReducedMotion) && (
          <path
            d={pathD}
            stroke="var(--ui-brand-pulse)"
            strokeWidth="5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={`transition-opacity duration-300 ${
              isFocused ? 'opacity-100' : 'opacity-95'
            }`}
          />
        )}

        {/* Entrance Drawing Animation (sweeps across like an ECG / seismic trace) */}
        {!prefersReducedMotion && !animationComplete && (
          <motion.path
            d={pathD}
            stroke="var(--ui-brand-pulse)"
            strokeWidth="5"
            strokeLinecap="round"
            strokeLinejoin="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{
              duration: 1.2,
              ease: [0.22, 1, 0.36, 1],
            }}
            onAnimationComplete={() => setAnimationComplete(true)}
          />
        )}
      </svg>
    </div>
  );
};
