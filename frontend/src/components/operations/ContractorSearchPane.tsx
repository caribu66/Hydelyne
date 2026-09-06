import { FC, useState, useMemo, useCallback, ReactNode, FormEvent, lazy, Suspense } from 'react'
import {
  Columns,
  Filter,
  LayoutGrid,
  Search,
  Table,
  UserPlus,
  X,
  ArrowUpRight,
  ExternalLink,
} from 'lucide-react'
import { UserProfile } from '../../types'
import { SegmentedControl } from '../ui'

const SpecialistTableView = lazy(() =>
  import('../SpecialistTableView').then((module) => ({ default: module.SpecialistTableView }))
)

const SpecialistDossierPane = lazy(() =>
  import('../SpecialistDossierPane').then((module) => ({ default: module.SpecialistDossierPane }))
)

export type ContractorViewMode = 'split' | 'grid' | 'table'

interface ContractorSearchPaneProps {
  profiles: UserProfile[]
  loading?: boolean
  searchControl?: ReactNode
  viewMode?: ContractorViewMode
  onViewModeChange?: (mode: ContractorViewMode) => void
  onSelectProfile?: (profile: UserProfile) => void
  onMobilize?: (profile: UserProfile) => void
  onSearchFull?: (query: string) => void
  onShowToast?: (message: string) => void
  isBookmarked?: (id: string) => boolean
  onToggleBookmark?: (id: string, e?: React.MouseEvent) => void
  compareIds?: string[]
  onToggleCompare?: (profile: UserProfile) => void
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
  viewMode = 'grid',
  onViewModeChange,
  onSelectProfile,
  onMobilize,
  onSearchFull,
  onShowToast = () => {},
  isBookmarked = () => false,
  onToggleBookmark = () => {},
  compareIds = [],
  onToggleCompare,
}) => {
  const [query, setQuery] = useState('')
  const [selectedDiscipline, setSelectedDiscipline] = useState('all')
  const [useAdvancedSearch, setUseAdvancedSearch] = useState(false)
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null)

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

  const activeSplitProfile = useMemo(() => {
    if (!filteredProfiles.length) return null
    if (selectedProfileId) {
      const found = filteredProfiles.find((p) => p.id === selectedProfileId)
      if (found) return found
    }
    return filteredProfiles[0]
  }, [filteredProfiles, selectedProfileId])

  const activeIndex = useMemo(() => {
    if (!activeSplitProfile) return -1
    return filteredProfiles.findIndex((p) => p.id === activeSplitProfile.id)
  }, [filteredProfiles, activeSplitProfile])

  const handlePrevProfile = useCallback(() => {
    if (activeIndex > 0) {
      const prev = filteredProfiles[activeIndex - 1]
      if (prev) setSelectedProfileId(prev.id)
    }
  }, [activeIndex, filteredProfiles])

  const handleNextProfile = useCallback(() => {
    if (activeIndex >= 0 && activeIndex < filteredProfiles.length - 1) {
      const next = filteredProfiles[activeIndex + 1]
      if (next) setSelectedProfileId(next.id)
    }
  }, [activeIndex, filteredProfiles])

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (query.trim() && onSearchFull) {
      onSearchFull(query.trim())
    }
  }

  return (
    <div className="mt-3 flex flex-col gap-3.5">
      {/* Top Controls Row: Quick discipline chips + View Mode Switcher */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
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

        {/* View Mode Switcher: Split, Cards (Grid), Matrix (Table) */}
        <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
          <SegmentedControl<ContractorViewMode>
            label="Contractor view"
            value={viewMode}
            onChange={(m) => onViewModeChange?.(m)}
            className="inline-flex"
            options={[
              { value: 'split', label: 'Split', icon: <Columns className="h-3.5 w-3.5" aria-hidden="true" /> },
              { value: 'grid', label: 'Cards', icon: <LayoutGrid className="h-3.5 w-3.5" aria-hidden="true" /> },
              { value: 'table', label: 'Matrix', icon: <Table className="h-3.5 w-3.5" aria-hidden="true" /> },
            ]}
          />

          {searchControl && (
            <button
              type="button"
              onClick={() => setUseAdvancedSearch((prev) => !prev)}
              className="text-xs font-medium text-accent hover:underline hidden lg:inline-flex items-center gap-1 cursor-pointer"
            >
              {useAdvancedSearch ? 'Quick search' : 'Natural language'}
            </button>
          )}
        </div>
      </div>

      {useAdvancedSearch && searchControl ? (
        <div className="rounded-[10px] border border-border-subtle bg-surface-raised/30 p-3">
          {searchControl}
        </div>
      ) : (
        <div className="flex flex-col gap-2.5">
          {/* Quick Search Input */}
          <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
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
            {onSearchFull && query.trim() && (
              <button
                type="submit"
                className="inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg bg-action px-4 py-2 text-xs font-semibold text-on-action transition-colors hover:bg-action-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus cursor-pointer shrink-0"
              >
                <span>Search in workspace</span>
                <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            )}
          </form>

          {/* Results Summary */}
          <div className="flex items-center justify-between px-1 text-xs text-secondary">
            <span>
              Showing <strong className="font-semibold text-primary">{filteredProfiles.length}</strong>{' '}
              {filteredProfiles.length === 1 ? 'specialist' : 'specialists'}
              {selectedDiscipline !== 'all' && ' in filtered category'}
            </span>
            {onSearchFull && (
              <button
                type="button"
                onClick={() => onSearchFull(query.trim())}
                className="inline-flex items-center gap-1 text-accent font-medium hover:underline cursor-pointer"
              >
                <span>Open full database view</span>
                <ExternalLink className="h-3 w-3" aria-hidden="true" />
              </button>
            )}
          </div>

          {/* Content Views: Matrix (Table), Split, or Cards (Grid) */}
          {loading ? (
            <div className="rounded-[10px] border border-border-subtle bg-surface-raised/20 p-8 text-center text-xs text-muted">
              Loading specialists…
            </div>
          ) : filteredProfiles.length === 0 ? (
            <div className="rounded-[10px] border border-border-subtle bg-surface-raised/20 p-8 text-center text-xs text-muted">
              No specialists match the selected criteria. Try adjusting your search query or discipline filter.
            </div>
          ) : viewMode === 'table' ? (
            /* Matrix View (Table) */
            <div className="rounded-[10px] border border-border-subtle bg-surface overflow-hidden">
              <Suspense fallback={<div className="p-8 text-center text-xs text-muted">Loading spreadsheet matrix…</div>}>
                <SpecialistTableView
                  profiles={filteredProfiles}
                  searchQuery={query}
                  selectedId={selectedProfileId}
                  onSelectProfile={(p) => onSelectProfile?.(p)}
                  isBookmarked={isBookmarked}
                  onToggleBookmark={onToggleBookmark}
                  onShowToast={onShowToast}
                  compareIds={compareIds}
                  onToggleCompare={onToggleCompare}
                  onRequestMobilization={onMobilize}
                />
              </Suspense>
            </div>
          ) : viewMode === 'split' ? (
            /* Split View: Left roster column + Right live SpecialistDossierPane */
            <div className="grid grid-cols-1 md:grid-cols-12 gap-3.5 h-[660px]">
              {/* Left Candidate List */}
              <div className="md:col-span-5 lg:col-span-4 flex flex-col h-full border border-border-subtle rounded-[14px] bg-surface/50 p-2.5 overflow-hidden">
                <div className="flex items-center justify-between px-1 pb-2 border-b border-border-subtle/80 mb-2 shrink-0">
                  <span className="text-xs font-semibold text-primary">Specialist Roster</span>
                  <span className="font-mono text-[11px] text-muted">
                    {filteredProfiles.length} {filteredProfiles.length === 1 ? 'candidate' : 'candidates'}
                  </span>
                </div>
                <div className="flex-1 overflow-y-auto space-y-2 pr-1 scrollbar-thin">
                  {filteredProfiles.map((p) => {
                    const isSel = activeSplitProfile?.id === p.id
                    const isAvail = p.availability?.toLowerCase().includes('immediately')

                    return (
                      <div
                        key={p.id}
                        role="button"
                        tabIndex={0}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            setSelectedProfileId(p.id)
                          }
                        }}
                        onClick={() => {
                          setSelectedProfileId(p.id)
                          if (typeof window !== 'undefined' && window.matchMedia('(max-width: 767px)').matches) {
                            onSelectProfile?.(p)
                          }
                        }}
                        className={`group relative p-2.5 rounded-[10px] border transition-all cursor-pointer flex items-center justify-between gap-2.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-focus ${
                          isSel
                            ? 'bg-surface border-border-strong shadow-md ring-1 ring-border-strong'
                            : 'bg-surface/40 hover:bg-surface border-border-subtle/80 hover:border-border-subtle'
                        }`}
                      >
                        {/* Active selection indicator bar */}
                        <div
                          className={`absolute left-0 top-2 bottom-2 w-1 rounded-r-full transition-all duration-200 ${
                            isSel ? 'bg-primary opacity-100' : 'bg-transparent opacity-0'
                          }`}
                          aria-hidden="true"
                        />

                        <div className="flex items-center gap-2.5 min-w-0 flex-1 pl-1">
                          <div className="relative shrink-0">
                            <img
                              src={p.avatar}
                              alt={p.name}
                              referrerPolicy="no-referrer"
                              className="w-9 h-9 rounded-lg object-cover border border-border-subtle"
                            />
                            {isAvail && (
                              <span
                                className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-positive border-2 border-surface"
                                title="Available immediately"
                              />
                            )}
                          </div>

                          <div className="min-w-0 flex-1">
                            <div className="flex items-baseline justify-between gap-1">
                              <p className="font-semibold text-xs text-primary truncate">{p.name}</p>
                              {p.dayRate ? (
                                <span className="font-mono font-bold text-[11px] text-primary shrink-0">
                                  £{p.dayRate}/d
                                </span>
                              ) : null}
                            </div>
                            <p className="text-[11px] text-secondary truncate">{p.title}</p>
                            <div className="flex items-center gap-1.5 mt-0.5 text-[10px] text-muted font-mono truncate">
                              {p.location && <span>{p.location}</span>}
                              {p.location && p.department && <span>·</span>}
                              {p.department && <span>{p.department}</span>}
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Right Column: Full-Featured SpecialistDossierPane */}
              <div className="hidden md:flex md:col-span-7 lg:col-span-8 flex-col h-full min-w-0 overflow-hidden">
                <Suspense
                  fallback={
                    <div className="h-full min-h-[460px] animate-pulse bg-surface/40 rounded-[14px] border border-border-subtle flex items-center justify-center text-xs text-muted font-mono">
                      Loading dossier…
                    </div>
                  }
                >
                  <SpecialistDossierPane
                    profile={activeSplitProfile ?? null}
                    searchQuery={query}
                    isBookmarked={activeSplitProfile ? isBookmarked(activeSplitProfile.id) : false}
                    onToggleBookmark={onToggleBookmark}
                    onShowToast={onShowToast}
                    isCompared={activeSplitProfile ? compareIds.includes(activeSplitProfile.id) : false}
                    onToggleCompare={onToggleCompare}
                    onRequestMobilization={onMobilize}
                    onPrintDossier={onSelectProfile}
                    documents={[]}
                    summary={activeSplitProfile?.bio || activeSplitProfile?.professionalSummary}
                    summaryLoading={false}
                    profileIndex={activeIndex >= 0 ? activeIndex : undefined}
                    totalProfiles={filteredProfiles.length}
                    onPrevProfile={handlePrevProfile}
                    onNextProfile={handleNextProfile}
                  />
                </Suspense>
              </div>
            </div>
          ) : (
            /* Cards View (Grid) */
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[580px] overflow-y-auto pr-1">
              {filteredProfiles.map((p) => {
                const isAvail = p.availability?.toLowerCase().includes('immediately')
                const isOnTour =
                  p.availability?.toLowerCase().includes('employed') ||
                  p.availability?.toLowerCase().includes('assignment')

                return (
                  <div
                    key={p.id}
                    className="flex flex-col justify-between gap-2.5 rounded-[12px] border border-border-subtle bg-surface p-3.5 hover:border-border-strong hover:bg-surface-raised/40 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3 min-w-0">
                        <img
                          src={p.avatar}
                          alt={p.name}
                          referrerPolicy="no-referrer"
                          className="w-10 h-10 rounded-xl object-cover border border-border-subtle shrink-0 mt-0.5"
                        />
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
                          <span className="font-mono text-xs font-semibold text-primary">
                            £{p.dayRate}/d
                          </span>
                        ) : null}
                      </div>
                    </div>

                    {/* Skills pills */}
                    {p.skills && p.skills.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-0.5">
                        {p.skills.slice(0, 3).map((skill, idx) => (
                          <span
                            key={idx}
                            className="badge-neutral rounded px-1.5 py-0.5 text-[11px] font-mono text-muted truncate max-w-[110px]"
                          >
                            {skill}
                          </span>
                        ))}
                        {p.skills.length > 3 && (
                          <span className="text-[10px] text-muted self-center font-mono">
                            +{p.skills.length - 3} more
                          </span>
                        )}
                      </div>
                    )}

                    {/* Actions bar */}
                    <div className="flex items-center justify-between gap-2 pt-2 border-t border-border-subtle/60 text-xs">
                      {onSelectProfile && (
                        <button
                          type="button"
                          onClick={() => onSelectProfile(p)}
                          className="inline-flex min-h-8 items-center gap-1 rounded-md border border-border-subtle bg-surface-raised px-2.5 py-1 text-xs font-medium text-secondary hover:text-primary hover:bg-surface-selected transition-colors cursor-pointer"
                        >
                          <span>View profile</span>
                          <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
                        </button>
                      )}

                      {onMobilize && (
                        <button
                          type="button"
                          onClick={() => onMobilize(p)}
                          className="inline-flex min-h-8 items-center gap-1 rounded-md bg-action px-3 py-1 text-xs font-semibold text-on-action hover:bg-action-hover transition-colors cursor-pointer"
                          aria-label={`Mobilize ${p.name}`}
                        >
                          <UserPlus className="h-3 w-3" aria-hidden="true" />
                          <span>Mobilize</span>
                        </button>
                      )}
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
