import { FC, useState, useRef, FormEvent } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { Eye, EyeOff, Loader2, X } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../hooks/useTheme';
import hydenlyneLogoWhite from '../assets/hydenlyne-logo-white.png';
import hydenlyneLogoColour from '../assets/hydenlyne-logo-colour.png';
import { Button, Field, IconButton, StatusMessage } from './ui';

interface LoginPageProps {
  isOpen?: boolean;
  onSuccess: () => void;
  isModal?: boolean;
  onCancel?: () => void;
}

export const LoginPage: FC<LoginPageProps> = ({
  isOpen = true,
  onSuccess,
  isModal = false,
  onCancel,
}) => {
  const { login, loggingIn } = useAuth();
  const { isDark } = useTheme();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  useAccessibleDialog(isModal && isOpen, dialogRef, onCancel ?? (() => undefined));

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setMessage(null);
    if (!email || !password) {
      setMessage('Please enter your email and password.');
      return;
    }
    const res = await login(email, password, rememberMe);
    if (res.ok) onSuccess();
    else setMessage(res.message ?? 'Unable to sign in. Please check your details and try again.');
  };

  const formBody = (
    <>
      <div className="mb-7 text-center">
        <img
          src={isDark ? hydenlyneLogoWhite : hydenlyneLogoColour}
          alt="Hydenlyne"
          className="mx-auto w-[140px] h-auto"
        />
        <p className="mt-2.5 text-xs font-mono uppercase tracking-[0.16em] text-muted">
          Sign in to your account
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <Field
          id="login-email"
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="email"
          required
        />

        <div>
          <label htmlFor="login-password" className="mb-1.5 block text-xs font-medium text-secondary">
            Password
          </label>
          <div className="relative">
            <input
              id="login-password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              className="ui-control w-full px-3 pr-12 text-sm"
              required
            />
            <IconButton
              label={showPassword ? 'Hide password' : 'Show password'}
              onClick={() => setShowPassword((visible) => !visible)}
              className="absolute right-0 top-1/2 -translate-y-1/2 border-transparent"
            >
              {showPassword ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            </IconButton>
          </div>
        </div>

        {message && <StatusMessage tone="danger" role="alert" aria-live="polite">{message}</StatusMessage>}

        <div className="flex items-center justify-between pt-0.5">
          <label className="flex min-h-11 items-center gap-2 text-xs text-secondary cursor-pointer">
            <input
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="h-4 w-4 rounded border-border-strong text-action focus:ring-focus"
            />
            Remember me
          </label>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setMessage('Contact your Hydenlyne administrator to reset your password.')}
            className="underline underline-offset-2"
          >
            Forgot password?
          </Button>
        </div>

        <Button type="submit" variant="primary" disabled={loggingIn} className="mt-1 w-full min-h-11">
          {loggingIn && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {loggingIn ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>

      <p className="mt-8 text-center text-xs text-muted">
        Private workforce network. Access is protected.
      </p>
    </>
  );

  if (!isModal) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-canvas px-6 py-12 font-sans text-primary antialiased">
        <div className="w-[min(100%,360px)] rounded-[14px] border border-border-subtle bg-surface p-6 sm:p-8 shadow-2xl">
          {formBody}
        </div>
      </main>
    );
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 overflow-y-auto"
        >
          {/* Backdrop with fade */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 bg-canvas/80 backdrop-blur-xs"
            onClick={onCancel}
          />

          {/* Modal Container with smooth scale + slide */}
          <motion.div
            ref={dialogRef}
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            className="relative z-10 w-[min(100%,380px)] rounded-[14px] border border-border-subtle bg-surface p-6 sm:p-8 shadow-2xl text-primary my-auto"
            role="dialog"
            aria-modal="true"
            aria-label="Sign in"
            onClick={(e) => e.stopPropagation()}
          >
            {onCancel && (
              <IconButton
                label="Close dialog"
                onClick={onCancel}
                className="absolute right-4 top-4"
              >
                <X className="h-4 w-4" />
              </IconButton>
            )}
            {formBody}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};
