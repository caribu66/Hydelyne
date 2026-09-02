import { useEffect, useState } from 'react';
import { Bot, Cloud, Database, Server } from 'lucide-react';
import { GRAPHQL_URL } from '../config';
import { getAuthToken } from '../lib/apollo';

type ServiceName = 'database' | 'redis' | 'dropbox' | 'ollama';
type ServiceState = 'healthy' | 'unhealthy' | 'unconfigured' | 'checking';

const services: Array<{ name: ServiceName; label: string; icon: typeof Database }> = [
  { name: 'database', label: 'PostgreSQL', icon: Database },
  { name: 'redis', label: 'Redis', icon: Server },
  { name: 'dropbox', label: 'Dropbox', icon: Cloud },
  { name: 'ollama', label: 'AI / Ollama', icon: Bot },
];

const stateStyle: Record<ServiceState, string> = {
  healthy: 'border-positive-border/70 bg-positive-soft/40 text-positive',
  unhealthy: 'border-danger-border/70 bg-danger-soft/40 text-danger',
  unconfigured: 'border-warning-border/70 bg-warning-soft/40 text-warning',
  checking: 'border-border-strong bg-surface text-secondary',
};

export function ServiceStatus() {
  const [states, setStates] = useState<Record<ServiceName, ServiceState>>({
    database: 'checking', redis: 'checking', dropbox: 'checking', ollama: 'checking',
  });

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const token = getAuthToken();
        const response = await fetch(`${GRAPHQL_URL.replace(/\/graphql\/?$/, '')}/health/services`, {
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
          credentials: 'include',
        });
        if (!response.ok) throw new Error('Health check failed');
        const body = await response.json() as { services: Record<ServiceName, ServiceState> };
        if (!cancelled) setStates(body.services);
      } catch {
        if (!cancelled) setStates({ database: 'unhealthy', redis: 'unhealthy', dropbox: 'unhealthy', ollama: 'unhealthy' });
      }
    };
    void check();
    const timer = window.setInterval(() => void check(), 15_000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, []);

  const announcement = services.map(({ name, label }) => `${label}: ${states[name]}`).join(', ');

  return (
    <div className="hidden lg:flex items-center gap-1 rounded-[10px] border border-border-subtle bg-canvas/60 p-1" aria-label="Live service status">
      <span className="sr-only" role="status" aria-live="polite" aria-atomic="true">Services: {announcement}</span>
      {services.map(({ name, label, icon: Icon }) => {
        const state = states[name];
        return (
          <span key={name} title={`${label}: ${state}`} className={`inline-flex h-8 w-8 items-center justify-center rounded-lg border ${stateStyle[state]}`}>
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="sr-only">{label}: {state}</span>
          </span>
        );
      })}
    </div>
  );
}
