import { FC, useState, useRef, FormEvent } from 'react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { Eye, EyeOff, Loader2, X } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../hooks/useTheme';
import hydenlyneLogoWhite from '../assets/hydenlyne-logo-white.png';
import hydenlyneLogoColour from '../assets/hydenlyne-logo-colour.png';
import { Button, Field, IconButton, StatusMessage } from './ui';

interface LoginPageProps {
  onSuccess: () => void;
  isModal?: boolean;
  onCancel?: () => void;
}

export const LoginPage: FC<LoginPageProps> = ({ onSuccess, isModal = false, onCancel }) => {
  const { login, loggingIn } = useAuth();
  const { isDark } = useTheme();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  useAccessibleDialog(isModal, dialogRef, onCancel ?? (() => undefined));

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

  return (
    <main className={`${isModal ? 'fixed inset-0 z-50' : 'min-h-screen'} flex items-center justify-center bg-canvas px-6 py-12 font-sans text-primary antialiased`}>
      {isModal && onCancel && (
        <IconButton label="Close sign in" onClick={onCancel} className="absolute right-4 top-4 sm:right-6 sm:top-6">
          <X className="h-4 w-4" />
        </IconButton>
      )}
      <div ref={dialogRef} className="w-[min(100%,340px)]" role={isModal ? 'dialog' : undefined} aria-modal={isModal || undefined} aria-label={isModal ? 'Sign in' : undefined}>
        <div className="mb-9 text-center">
          <img src={isDark ? hydenlyneLogoWhite : hydenlyneLogoColour} alt="Hydenlyne" className="mx-auto w-[150px] h-auto" />
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Field id="login-email" label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />

          <div>
            <label htmlFor="login-password" className="mb-1.5 block text-xs font-medium text-secondary">Password</label>
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
              <IconButton label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword((visible) => !visible)} className="absolute right-0 top-1/2 -translate-y-1/2 border-transparent">
                {showPassword ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </IconButton>
            </div>
          </div>

          {message && <StatusMessage tone="danger" role="alert" aria-live="polite">{message}</StatusMessage>}

          <div className="flex items-center justify-between pt-0.5">
            <label className="flex min-h-11 items-center gap-2 text-xs text-secondary cursor-pointer">
              <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} className="h-4 w-4 accent-zinc-100" />
              Remember me
            </label>
            <Button variant="ghost" size="sm" onClick={() => setMessage('Contact your Hydenlyne administrator to reset your password.')} className="underline underline-offset-2">Forgot password?</Button>
          </div>

          <Button type="submit" variant="primary" disabled={loggingIn} className="mt-1 min-w-24">
            {loggingIn && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {loggingIn ? 'Signing in…' : 'Sign in'}
          </Button>
        </form>

        <p className="mt-10 text-center text-xs text-secondary">
          Private workforce system · Access is monitored
        </p>
      </div>
    </main>
  );
};
