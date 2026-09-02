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
  healthy: 'border-emerald-800/70 bg-emerald-950/40 text-emerald-300',
  unhealthy: 'border-rose-800/70 bg-rose-950/40 text-rose-300',
  unconfigured: 'border-amber-800/70 bg-amber-950/40 text-amber-300',
  checking: 'border-zinc-700 bg-zinc-900 text-zinc-400',
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

  return (
    <div className="hidden lg:flex items-center gap-1 rounded-xl border border-zinc-800 bg-zinc-950/60 p-1" aria-label="Live service status">
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
