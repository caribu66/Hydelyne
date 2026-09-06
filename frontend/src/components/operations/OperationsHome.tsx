import { FC, ReactNode, useEffect, useState } from 'react'
import { motion } from 'motion/react'
import { useQuery } from '@apollo/client'
import { Ship, Users } from 'lucide-react'
import { OperationsGreeting } from './OperationsGreeting'
import { OperationsAttention } from './OperationsAttention'
import { OperationsMetrics } from './OperationsMetrics'
import { OperationsProjectsPanel } from './OperationsProjectsPanel'
import { VesselSearchPane } from './VesselSearchPane'
import { ContractorSearchPane } from './ContractorSearchPane'
import { deriveCrewReadinessMetrics, formatExpiringCertSearchQuery } from '../../utils/operationsHome'
import { UserProfile } from '../../types'
import { EXPIRING_CERTS_QUERY } from '../../lib/queries'
import { incomingDocumentReviews } from '../../lib/documentsApi'

interface OperationsHomeProps {
  fullName: string | null | undefined
  profiles: UserProfile[]
  profilesLoading: boolean
  profilesError: string | null
  onSearch: (query: string) => void
  onOpenDocumentReview: () => void
  documentReviewVersion: number
  isStaff: boolean
  searchControl: ReactNode
  onShowToast?: (message: string) => void
  onSelectProfile?: (profile: UserProfile) => void
  onMobilizeProfile?: (profile: UserProfile) => void
  viewMode?: 'split' | 'grid' | 'table'
  onViewModeChange?: (mode: 'split' | 'grid' | 'table') => void
  isBookmarked?: (id: string) => boolean
  onToggleBookmark?: (id: string, e?: React.MouseEvent) => void
  compareIds?: string[]
  onToggleCompare?: (profile: UserProfile) => void
}

export const OperationsHome: FC<OperationsHomeProps> = ({
  fullName,
  profiles,
  profilesLoading,
  profilesError,
  onSearch,
  onOpenDocumentReview,
  documentReviewVersion,
  isStaff,
  searchControl,
  onShowToast,
  onSelectProfile,
  onMobilizeProfile,
  viewMode,
  onViewModeChange,
  isBookmarked,
  onToggleBookmark,
  compareIds,
  onToggleCompare,
}) => {
  const metrics = deriveCrewReadinessMetrics(profiles)

  const [searchTab, setSearchTab] = useState<'contractors' | 'vessels'>(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      if (params.get('tab') === 'vessels' || params.get('vessel')) {
        return 'vessels'
      }
    }
    return 'contractors'
  })

  // Documents queue (REST)
  const [docCount, setDocCount] = useState<number | null>(null)
  const [docLoading, setDocLoading] = useState(true)
  const [docError, setDocError] = useState<string | null>(null)

  useEffect(() => {
    if (!isStaff) {
      setDocLoading(false)
      setDocCount(0)
      return
    }
    let active = true
    const load = async () => {
      try {
        setDocLoading(true)
        const items = await incomingDocumentReviews()
        if (active) {
          setDocCount(items.length)
          setDocError(null)
        }
      } catch (err) {
        if (active) {
          setDocError(err instanceof Error ? err.message : 'Could not load documents')
          setDocCount(null)
        }
      } finally {
        if (active) setDocLoading(false)
      }
    }
    void load()
    return () => {
      active = false
    }
  }, [documentReviewVersion, isStaff])

  // Expiring certifications (GraphQL, staff only)
  const {
    data: expiringData,
    loading: expiringLoading,
    error: expiringError,
  } = useQuery<{ expiringCertifications: Array<{ id: string }> }>(EXPIRING_CERTS_QUERY, {
    variables: { days: 60 },
    fetchPolicy: 'cache-and-network',
    skip: !isStaff,
  })

  const expiringCount = expiringData?.expiringCertifications?.length ?? null
  const expiringErrorMessage = expiringError ? expiringError.message : null

  const handleOpenExpiring = () => {
    onSearch(formatExpiringCertSearchQuery())
  }

  const containerVariants = {
    hidden: {},
    visible: { transition: { staggerChildren: 0.06, delayChildren: 0.02 } },
  } as const

  const itemVariants = {
    hidden: { opacity: 0, y: 8 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.20, ease: [0.22, 1, 0.36, 1] as const },
    },
  }

  return (
    <motion.div
      className="w-full space-y-6 py-6"
      aria-label="Operations overview"
      initial="hidden"
      animate="visible"
      variants={containerVariants}
    >
      <motion.div variants={itemVariants}>
        <OperationsGreeting fullName={fullName} />
      </motion.div>

      {!isStaff && (
        <motion.p
          variants={itemVariants}
          className="rounded-[14px] border border-border-subtle bg-surface/40 px-4 py-6 text-center text-sm text-muted"
        >
          Use the search below to explore the private specialist network.
        </motion.p>
      )}

      {/* Primary Operations Command Center: Search & Mobilization Hub */}
      <motion.section
        variants={itemVariants}
        aria-label="Operations search and tracking hub"
        className="rounded-[14px] border border-border-subtle bg-surface p-4 sm:p-5 shadow-xs"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border-subtle/80 pb-3.5 mb-4">
          <div
            role="tablist"
            aria-label="Operations search mode"
            onKeyDown={(e) => {
              if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
                e.preventDefault()
                setSearchTab((prev) => (prev === 'contractors' ? 'vessels' : 'contractors'))
              }
            }}
            className="inline-flex rounded-lg bg-surface-raised p-1 border border-border-subtle/60"
          >
            <button
              type="button"
              role="tab"
              id="tab-contractors"
              aria-selected={searchTab === 'contractors'}
              aria-controls="panel-contractors"
              onClick={() => setSearchTab('contractors')}
              className={`inline-flex min-h-9 items-center gap-2 rounded-md px-3.5 py-1.5 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus cursor-pointer ${
                searchTab === 'contractors'
                  ? 'bg-surface text-primary shadow-xs border border-border-subtle/80'
                  : 'text-secondary hover:text-primary hover:bg-surface-raised/60'
              }`}
            >
              <Users className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
              <span>Find a contractor</span>
            </button>
            <button
              type="button"
              role="tab"
              id="tab-vessels"
              aria-selected={searchTab === 'vessels'}
              aria-controls="panel-vessels"
              onClick={() => setSearchTab('vessels')}
              className={`inline-flex min-h-9 items-center gap-2 rounded-md px-3.5 py-1.5 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus cursor-pointer ${
                searchTab === 'vessels'
                  ? 'bg-surface text-primary shadow-xs border border-border-subtle/80'
                  : 'text-secondary hover:text-primary hover:bg-surface-raised/60'
              }`}
            >
              <Ship className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
              <span>Find a vessel</span>
            </button>
          </div>

          <div className="flex items-center gap-2 text-xs font-mono text-muted">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-positive" aria-hidden="true" />
            <span>
              {searchTab === 'contractors' ? 'Specialist network & live mobilization' : 'Live AIS tracking & rosters'}
            </span>
          </div>
        </div>

        {searchTab === 'contractors' ? (
          <div
            id="panel-contractors"
            role="tabpanel"
            aria-labelledby="tab-contractors"
            tabIndex={0}
            className="focus-visible:outline-none"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <h2 id="find-contractor-heading" className="text-sm font-semibold text-primary">
                Find a contractor
              </h2>
              <span className="font-mono text-xs text-muted">Specialist network</span>
            </div>
            <p className="mt-1 text-sm text-secondary">
              Search by discipline, certification, region, and availability — try "Available hydrography surveyors
              with BOSIET in the North Sea".
            </p>
            <ContractorSearchPane
              profiles={profiles}
              loading={profilesLoading}
              searchControl={searchControl}
              viewMode={viewMode}
              onViewModeChange={onViewModeChange}
              onSelectProfile={onSelectProfile}
              onMobilize={onMobilizeProfile}
              onSearchFull={onSearch}
              onShowToast={onShowToast}
              isBookmarked={isBookmarked}
              onToggleBookmark={onToggleBookmark}
              compareIds={compareIds}
              onToggleCompare={onToggleCompare}
            />
          </div>
        ) : (
          <div
            id="panel-vessels"
            role="tabpanel"
            aria-labelledby="tab-vessels"
            tabIndex={0}
            className="focus-visible:outline-none"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <h2 id="find-vessel-heading" className="text-sm font-semibold text-primary">
                Find a vessel
              </h2>
              <span className="font-mono text-xs text-muted">AIS tracking & mobilization</span>
            </div>
            <p className="mt-1 text-sm text-secondary">
              Search by vessel name, IMO, MMSI, or callsign — live AIS data via VesselAPI with active mobilization rosters.
            </p>
            <VesselSearchPane onShowToast={onShowToast} />
          </div>
        )}
      </motion.section>

      {/* Operations Telemetry: Metrics ribbon & operational action boards */}
      {isStaff ? (
        <>
          <motion.div variants={itemVariants}>
            <OperationsMetrics
              available={metrics.available}
              onAssignment={metrics.onAssignment}
              unavailable={metrics.unavailable}
              total={metrics.total}
              loading={profilesLoading}
              error={profilesError}
              onSelectStatus={onSearch}
            />
          </motion.div>

          <motion.div variants={itemVariants} className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <OperationsAttention
              documents={{ count: docCount, loading: docLoading, error: docError }}
              expiring={{ count: expiringCount, loading: expiringLoading, error: expiringErrorMessage }}
              onOpenDocuments={onOpenDocumentReview}
              onOpenExpiring={handleOpenExpiring}
            />
            <OperationsProjectsPanel
              onSelectProject={(query) => {
                onSearch(query)
              }}
            />
          </motion.div>
        </>
      ) : null}

    </motion.div>
  )
}
