import './initTheme';
import { StrictMode, lazy, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import { ApolloProvider } from '@apollo/client';
import { MotionConfig } from 'motion/react';
import { apolloClient } from './lib/apollo';
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
const uploadToken = uploadMatch?.[1] ? decodeURIComponent(uploadMatch[1]) : undefined;
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
        <Suspense
          fallback={
            <div className="flex h-screen w-screen items-center justify-center bg-canvas text-secondary">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-action border-t-transparent" />
            </div>
          }
        >
          {root}
        </Suspense>
      </ApolloProvider>
    </MotionConfig>
  </StrictMode>,
);
