import './initTheme';
import { StrictMode, lazy, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import { ApolloProvider } from '@apollo/client';
import { MotionConfig } from 'motion/react';
import { apolloClient } from './lib/apollo';
import { decodeUploadTokenSegment } from './utils/uploadRoute';
import { AuthProvider } from './hooks/useAuth';
import './index.css';

const App = lazy(() => import('./App.tsx'));
const ContractorDocumentUploadPage = lazy(() =>
  import('./components/ContractorDocumentUploadPage.tsx').then((module) => ({
    default: module.ContractorDocumentUploadPage,
  })),
);

const rootElement = document.getElementById('root');
if (!rootElement) throw new Error('Root container element #root not found');

const uploadMatch = window.location.pathname.match(/^\/upload\/([^/]+)\/?$/);
const uploadToken = uploadMatch?.[1] ? decodeUploadTokenSegment(uploadMatch[1]) : undefined;
const root = uploadToken ? <ContractorDocumentUploadPage token={uploadToken} /> : <App />;

createRoot(rootElement).render(
  <StrictMode>
    {/* "user" defers to the OS/browser prefers-reduced-motion setting at
        runtime — this is what actually makes Framer Motion honor it. The
        CSS media query in index.css only ever covered native CSS
        animations/transitions, not Framer Motion's own transform/opacity
        driving, which is most of this app's motion. */}
    <MotionConfig reducedMotion="user">
      <ApolloProvider client={apolloClient}>
        <AuthProvider>
          <Suspense
            fallback={
              <div className="flex min-h-screen flex-col bg-canvas font-sans text-primary antialiased">
                <main
                  id="main-content"
                  className="mx-auto flex w-full max-w-7xl flex-1 flex-col items-center justify-center px-4 py-12 sm:px-6"
                  aria-label="Contractor network workspace"
                >
                  <h1 className="mx-auto max-w-xl text-center text-3xl sm:text-4xl lg:text-[2.65rem] lg:leading-[1.12] font-semibold tracking-[-0.03em] text-primary">
                    Find the right contractor for the next campaign.
                  </h1>
                  <p className="mt-3 max-w-md text-center text-sm leading-relaxed text-secondary">
                    Search Hydenlyne&apos;s private specialist network by discipline, certification, region, and availability.
                  </p>
                  <div
                    className="mt-8 flex items-center gap-2 text-xs text-muted font-mono"
                    role="status"
                    aria-live="polite"
                  >
                    <span className="h-2 w-2 rounded-full bg-action animate-pulse" aria-hidden="true" />
                    Loading workspace…
                  </div>
                  <p className="mt-6 text-center text-xs text-muted">Private workforce network. Access is protected.</p>
                </main>
              </div>
            }
          >
            {root}
          </Suspense>
        </AuthProvider>
      </ApolloProvider>
    </MotionConfig>
  </StrictMode>,
);
