import { FC } from 'react';
import { escapeRegExp, getSearchTerms } from '../utils/searchTerms';

interface HighlightTextProps {
  text: string;
  query: string;
  className?: string;
}

export const HighlightText: FC<HighlightTextProps> = ({
  text,
  query,
  className = '',
}) => {
  if (!query || !query.trim() || !text) {
    return <span className={className}>{text}</span>;
  }

  const terms = getSearchTerms(query);

  if (terms.length === 0) {
    return <span className={className}>{text}</span>;
  }

  // Use the same meaningful terms as filtering. They are longest-first so an
  // overlapping shorter query term cannot create a partial highlight.
  const escapedTerms = terms.map(escapeRegExp);
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
              className="search-highlight"
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
