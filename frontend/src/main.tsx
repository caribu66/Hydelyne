import './initTheme';
import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import {ApolloProvider} from '@apollo/client';
import {MotionConfig} from 'motion/react';
import {apolloClient} from './lib/apollo';
import App from './App.tsx';
import './index.css';

const rootElement = document.getElementById('root');
if (!rootElement) throw new Error('Root container element #root not found');

createRoot(rootElement).render(
  <StrictMode>
    {/* "user" defers to the OS/browser prefers-reduced-motion setting at
        runtime — this is what actually makes Framer Motion honor it. The
        CSS media query in index.css only ever covered native CSS
        animations/transitions, not Framer Motion's own transform/opacity
        driving, which is most of this app's motion. */}
    <MotionConfig reducedMotion="user">
      <ApolloProvider client={apolloClient}>
        <App />
      </ApolloProvider>
    </MotionConfig>
  </StrictMode>,
);
