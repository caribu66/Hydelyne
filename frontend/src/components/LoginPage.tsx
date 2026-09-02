import { FC, useState, useRef, FormEvent } from 'react';
import { useAccessibleDialog } from '../hooks/useAccessibleDialog';
import { Eye, EyeOff, Loader2, X } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../hooks/useTheme';
import hydenlyneLogoWhite from '../assets/hydenlyne-logo-white.png';
import hydenlyneLogoColour from '../assets/hydenlyne-logo-colour.png';

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
    <main className={`${isModal ? 'fixed inset-0 z-50' : 'min-h-screen'} bg-zinc-950 px-6 py-12 text-zinc-100 font-sans antialiased flex items-center justify-center`}>
      {isModal && onCancel && (
        <button type="button" onClick={onCancel} aria-label="Close sign in" className="absolute right-4 top-4 inline-flex min-h-11 min-w-11 items-center justify-center rounded-xl text-zinc-500 transition-colors hover:bg-zinc-900 hover:text-zinc-200 cursor-pointer sm:right-6 sm:top-6">
          <X className="h-4 w-4" />
        </button>
      )}
      <div ref={dialogRef} className="w-[min(100%,340px)]" role={isModal ? 'dialog' : undefined} aria-modal={isModal || undefined} aria-label={isModal ? 'Sign in' : undefined}>
        <div className="mb-9 text-center">
          <img src={isDark ? hydenlyneLogoWhite : hydenlyneLogoColour} alt="Hydenlyne" className="mx-auto w-[150px] h-auto" />
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="login-email" className="mb-1.5 block text-xs font-medium text-zinc-400">Email</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              className="h-11 w-full rounded-xl border border-zinc-700 bg-zinc-900 px-3 text-sm text-zinc-100 outline-none transition-shadow placeholder:text-zinc-600 focus:border-zinc-500 focus:ring-2 focus:ring-zinc-500/20"
              required
            />
          </div>

          <div>
            <label htmlFor="login-password" className="mb-1.5 block text-xs font-medium text-zinc-400">Password</label>
            <div className="relative">
              <input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                className="h-11 w-full rounded-xl border border-zinc-700 bg-zinc-900 px-3 pr-12 text-sm text-zinc-100 outline-none transition-shadow placeholder:text-zinc-600 focus:border-zinc-500 focus:ring-2 focus:ring-zinc-500/20"
                required
              />
              <button type="button" aria-label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword((visible) => !visible)} className="absolute right-0 top-1/2 inline-flex min-h-11 min-w-11 -translate-y-1/2 items-center justify-center text-zinc-500 hover:text-zinc-200 cursor-pointer">
                {showPassword ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>

          {message && <div role="alert" aria-live="polite" className="border border-rose-800/60 bg-rose-950/40 px-3 py-2.5 text-xs leading-4 text-rose-300">{message}</div>}

          <div className="flex items-center justify-between pt-0.5">
            <label className="flex min-h-11 items-center gap-2 text-xs text-zinc-400 cursor-pointer">
              <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} className="h-4 w-4 accent-zinc-100" />
              Remember me
            </label>
            <button type="button" onClick={() => setMessage('Please contact your Hydenlyne administrator to reset your password.')} className="min-h-11 text-xs text-zinc-400 hover:text-zinc-200 underline underline-offset-2 cursor-pointer">Forgot password?</button>
          </div>

          <button type="submit" disabled={loggingIn} className="mt-1 inline-flex h-11 min-w-[70px] items-center justify-center gap-1.5 rounded-xl bg-zinc-100 px-4 text-xs font-semibold text-zinc-950 transition-colors hover:bg-white disabled:opacity-60 cursor-pointer">
            {loggingIn && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {loggingIn ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="mt-10 text-center text-xs text-zinc-400">
          Private workforce system · Access is monitored
        </p>
      </div>
    </main>
  );
};
