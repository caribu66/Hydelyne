import React from 'react';

interface HighlightTextProps {
  text: string;
  query: string;
  className?: string;
}

export const HighlightText: React.FC<HighlightTextProps> = ({
  text,
  query,
  className = '',
}) => {
  if (!query || !query.trim() || !text) {
    return <span className={className}>{text}</span>;
  }

  const terms = query
    .trim()
    .toLowerCase()
    .split(/[\s,]+/)
    .filter((t) => t.length > 1 && !['in', 'at', 'with', 'for', 'and', 'the', 'of', 'to'].includes(t));

  if (terms.length === 0) {
    return <span className={className}>{text}</span>;
  }

  // Create regex from terms
  const escapedTerms = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const regex = new RegExp(`(${escapedTerms.join('|')})`, 'gi');

  const parts = text.split(regex);

  return (
    <span className={className}>
      {parts.map((part, i) => {
        const isMatch = terms.some((t) => t.toLowerCase() === part.toLowerCase());
        if (isMatch) {
          return (
            <mark
              key={i}
              className="bg-blue-500/20 text-blue-200 font-medium px-1 py-0.5 rounded-xs"
            >
              {part}
            </mark>
          );
        }
        return part;
      })}
    </span>
  );
};
