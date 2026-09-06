import { FC, useState, useMemo, ReactNode } from 'react'
import { Filter, Search, UserPlus, X, ArrowUpRight } from 'lucide-react'
import { UserProfile } from '../../types'

interface ContractorSearchPaneProps {
  profiles: UserProfile[]
  loading?: boolean
  searchControl?: ReactNode
  onSelectProfile?: (profile: UserProfile) => void
  onMobilize?: (profile: UserProfile) => void
  onSearchFull?: (query: string) => void
}

const DISCIPLINE_CHIPS = [
  { id: 'all', label: 'All specialists' },
  { id: 'available', label: 'Available now' },
  { id: 'mmo', label: 'MMO / PAM', keyword: 'MMO' },
  { id: 'hydrography', label: 'Hydrography', keyword: 'Hydrograph' },
  { id: 'seismic', label: 'Seismic QC', keyword: 'Seismic' },
  { id: 'client_rep', label: 'Client Rep', keyword: 'Client Rep' },
  { id: 'geotech', label: 'Geotech', keyword: 'Geotech' },
  { id: 'hse', label: 'HSE / Safety', keyword: 'HSE' },
]

export const ContractorSearchPane: FC<ContractorSearchPaneProps> = ({
  profiles,
  loading = false,
  searchControl,
  onSelectProfile,
  onMobilize,
  onSearchFull,
}) => {
  const [query, setQuery] = useState('')
  const [selectedDiscipline, setSelectedDiscipline] = useState('all')
  const [useAdvancedSearch, setUseAdvancedSearch] = useState(false)

  const filteredProfiles = useMemo(() => {
    let list = profiles

    // Filter by discipline chip
    if (selectedDiscipline === 'available') {
      list = list.filter((p) => p.availability?.toLowerCase().includes('immediately'))
    } else if (selectedDiscipline !== 'all') {
      const chip = DISCIPLINE_CHIPS.find((c) => c.id === selectedDiscipline)
      if (chip?.keyword) {
        const kw = chip.keyword.toLowerCase()
        list = list.filter((p) => {
          const text = `${p.title || ''} ${p.department || ''} ${(p.skills || []).join(' ')} ${(p.expertise || []).join(' ')}`.toLowerCase()
          return text.includes(kw)
        })
      }
    }

    // Filter by query term
    const trimmed = query.trim().toLowerCase()
    if (trimmed) {
      list = list.filter((p) => {
        const full = `${p.name || ''} ${p.title || ''} ${p.department || ''} ${p.location || ''} ${(p.skills || []).join(' ')}`.toLowerCase()
        return full.includes(trimmed)
      })
    }

    return list
  }, [profiles, selectedDiscipline, query])

  return (
    <div className="mt-3 flex flex-col gap-3">
      {/* Header with toggle */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        {/* Quick discipline chips */}
        <div className="flex flex-wrap items-center gap-1.5 pb-0.5">
          <span className="text-xs text-muted flex items-center gap-1 mr-1">
            <Filter className="h-3 w-3" aria-hidden="true" />
            Discipline:
          </span>
          {DISCIPLINE_CHIPS.map((chip) => {
            const isActive = selectedDiscipline === chip.id
            return (
              <button
                key={chip.id}
                type="button"
                onClick={() => setSelectedDiscipline(chip.id)}
                className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${
                  isActive
                    ? 'bg-accent-soft border border-border-strong text-accent font-semibold shadow-xs'
                    : 'bg-surface-raised border border-border-subtle text-secondary hover:text-primary hover:bg-surface-selected'
                }`}
              >
                {chip.label}
              </button>
            )
          })}
        </div>

        {searchControl && (
          <button
            type="button"
            onClick={() => setUseAdvancedSearch((prev) => !prev)}
            className="text-xs font-medium text-accent hover:underline inline-flex items-center gap-1 cursor-pointer"
          >
            {useAdvancedSearch ? 'Switch to quick specialist cards' : 'Open natural language search bar'}
          </button>
        )}
      </div>

      {useAdvancedSearch && searchControl ? (
        <div className="rounded-[10px] border border-border-subtle bg-surface-raised/30 p-3">
          {searchControl}
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {/* Quick Search Input */}
          <div className="relative">
            <label htmlFor="contractor-search-input" className="sr-only">
              Search contractors
            </label>
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-muted">
              <Search className="h-4 w-4" aria-hidden="true" />
            </div>
            <input
              id="contractor-search-input"
              type="search"
              placeholder="Search contractor by name, role, skills, or region…"
              className="w-full min-h-11 rounded-lg border border-border-subtle bg-surface pl-10 pr-9 py-2 text-sm text-primary placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus transition-colors"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-muted hover:text-primary transition-colors cursor-pointer rounded-full"
                aria-label="Clear contractor search"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            )}
          </div>

          {/* Results Summary */}
          <div className="flex items-center justify-between px-1 text-xs text-secondary">
            <span>
              Showing <strong className="font-semibold text-primary">{filteredProfiles.length}</strong>{' '}
              {filteredProfiles.length === 1 ? 'specialist' : 'specialists'}
              {selectedDiscipline !== 'all' && ' in filtered category'}
            </span>
            {onSearchFull && query.trim() && (
              <button
                type="button"
                onClick={() => onSearchFull(query.trim())}
                className="inline-flex items-center gap-1 text-accent font-medium hover:underline cursor-pointer"
              >
                <span>Launch in full search view</span>
                <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
              </button>
            )}
          </div>

          {/* Specialist Cards Grid */}
          {loading ? (
            <div className="rounded-[10px] border border-border-subtle bg-surface-raised/20 p-8 text-center text-xs text-muted">
              Loading specialists…
            </div>
          ) : filteredProfiles.length === 0 ? (
            <div className="rounded-[10px] border border-border-subtle bg-surface-raised/20 p-8 text-center text-xs text-muted">
              No specialists match the selected criteria. Try adjusting your search query or discipline filter.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 max-h-[480px] overflow-y-auto pr-1">
              {filteredProfiles.slice(0, 16).map((p) => {
                const isAvail = p.availability?.toLowerCase().includes('immediately')
                const isOnTour = p.availability?.toLowerCase().includes('employed') || p.availability?.toLowerCase().includes('assignment')

                return (
                  <div
                    key={p.id}
                    className="flex flex-col justify-between gap-2.5 rounded-[10px] border border-border-subtle bg-surface p-3.5 hover:border-border-strong hover:bg-surface-raised/40 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <button
                          type="button"
                          onClick={() => onSelectProfile?.(p)}
                          className="text-left font-semibold text-sm text-primary hover:text-accent transition-colors truncate block cursor-pointer"
                        >
                          {p.name}
                        </button>
                        <p className="text-xs text-secondary truncate">{p.title}</p>
                        <p className="text-xs text-muted truncate mt-0.5">
                          {p.department || 'Marine Operations'} {p.location ? `· ${p.location}` : ''}
                        </p>
                      </div>

                      <div className="flex flex-col items-end gap-1 shrink-0">
                        <span
                          className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-mono font-medium ${
                            isAvail
                              ? 'bg-positive-soft text-positive border border-positive-border'
                              : isOnTour
                              ? 'bg-accent-soft text-accent border border-accent/30'
                              : 'bg-surface-raised text-muted border border-border-subtle'
                          }`}
                        >
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              isAvail ? 'bg-positive' : isOnTour ? 'bg-accent' : 'bg-muted'
                            }`}
                            aria-hidden="true"
                          />
                          {isAvail ? 'Available' : isOnTour ? 'On Tour' : 'Unavailable'}
                        </span>
                        {p.dayRate ? (
                          <span className="text-xs font-mono text-secondary">£{p.dayRate}/d</span>
                        ) : null}
                      </div>
                    </div>

                    {/* Skills pills & actions */}
                    <div className="flex items-center justify-between gap-2 pt-2 border-t border-border-subtle/50 text-xs">
                      <div className="flex flex-wrap gap-1 min-w-0 overflow-hidden">
                        {(p.skills || []).slice(0, 3).map((skill, idx) => (
                          <span
                            key={idx}
                            className="badge-neutral rounded px-1.5 py-0.5 text-[11px] font-mono text-muted truncate max-w-[110px]"
                          >
                            {skill}
                          </span>
                        ))}
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        {onMobilize && (
                          <button
                            type="button"
                            onClick={() => onMobilize(p)}
                            className="inline-flex min-h-8 items-center gap-1 rounded-md bg-accent-soft/60 border border-accent/40 px-2 py-0.5 text-xs font-semibold text-accent hover:bg-accent-soft transition-colors cursor-pointer"
                            aria-label={`Mobilize ${p.name}`}
                          >
                            <UserPlus className="h-3 w-3" aria-hidden="true" />
                            <span>Mobilize</span>
                          </button>
                        )}
                        {onSelectProfile && (
                          <button
                            type="button"
                            onClick={() => onSelectProfile(p)}
                            className="inline-flex min-h-8 items-center rounded-md border border-border-subtle bg-surface-raised px-2 py-0.5 text-xs font-medium text-secondary hover:text-primary hover:bg-surface-selected transition-colors cursor-pointer"
                          >
                            View
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
