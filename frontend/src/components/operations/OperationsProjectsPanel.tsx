import { FC } from 'react'
import { useQuery } from '@apollo/client'
import { MapPin, Calendar, Building2, ChevronRight, Loader2 } from 'lucide-react'
import { PROJECTS_QUERY } from '../../lib/queries'
import { formatProjectSearchQuery } from '../../utils/operationsHome'

interface ProjectDTO {
  id: string
  clientName: string
  projectName: string
  projectType: string
  location?: string | null
  country?: string | null
  startDate?: string | null
  endDate?: string | null
  status: string
}

interface OperationsProjectsPanelProps {
  onSelectProject: (query: string) => void
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
}

export const OperationsProjectsPanel: FC<OperationsProjectsPanelProps> = ({ onSelectProject }) => {
  const { data, loading, error } = useQuery<{ projects: ProjectDTO[] }>(PROJECTS_QUERY, {
    variables: { status: 'ACTIVE' },
    fetchPolicy: 'cache-and-network',
  })

  const projects = data?.projects ?? []

  return (
    <section aria-labelledby="projects-heading" className="rounded-[14px] border border-border-subtle bg-surface p-4 sm:p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 id="projects-heading" className="text-sm font-semibold text-primary">
          Active projects
        </h2>
        <span className="font-mono text-xs text-muted">
          {loading ? 'Loading…' : `${projects.length} ${projects.length === 1 ? 'project' : 'projects'}`}
        </span>
      </div>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted" role="status" aria-live="polite">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Loading projects…
        </div>
      ) : error ? (
        <p className="rounded-[10px] border border-border-subtle bg-surface-raised/40 px-3 py-8 text-center text-sm text-muted">
          Project data is unavailable
        </p>
      ) : projects.length === 0 ? (
        <p className="rounded-[10px] border border-border-subtle bg-surface-raised/40 px-3 py-8 text-center text-sm text-muted">
          No active projects
        </p>
      ) : (
        <ul className="space-y-2">
          {projects.slice(0, 6).map((project) => {
            const searchQuery = formatProjectSearchQuery(project)
            return (
              <li key={project.id} className="rounded-[10px] border border-border-subtle bg-surface-raised/20 p-3 transition-colors hover:border-border-strong hover:bg-surface-raised/40">
                <button
                  type="button"
                  onClick={() => {
                    if (searchQuery) onSelectProject(searchQuery)
                  }}
                  className="flex w-full items-start justify-between gap-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus rounded-lg"
                  aria-label={`Find contractors for ${project.projectName}`}
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-primary">{project.projectName}</p>
                    <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-secondary">
                      <span className="inline-flex items-center gap-1">
                        <Building2 className="h-3 w-3 text-muted" aria-hidden="true" />
                        {project.clientName}
                      </span>
                      <span className="text-muted">·</span>
                      <span className="capitalize">{project.projectType.replaceAll('_', ' ')}</span>
                    </p>
                    <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
                      {(project.location || project.country) && (
                        <span className="inline-flex items-center gap-1">
                          <MapPin className="h-3 w-3" aria-hidden="true" />
                          {project.location || project.country}
                        </span>
                      )}
                      <span className="inline-flex items-center gap-1">
                        <Calendar className="h-3 w-3" aria-hidden="true" />
                        {formatDate(project.startDate)} – {formatDate(project.endDate)}
                      </span>
                      <span className="inline-flex items-center rounded-full border border-border-subtle bg-surface-raised px-1.5 py-0.5 font-mono text-xs capitalize text-secondary">
                        {project.status}
                      </span>
                    </p>
                  </div>
                  <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-border-subtle bg-surface text-muted">
                    <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
