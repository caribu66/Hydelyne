import { FC } from 'react';
import { Check } from 'lucide-react';

interface ToastProps {
  message: string | null;
  onClose?: () => void;
}

export const Toast: FC<ToastProps> = ({ message }) => {
  if (!message) return null;

  return (
    <div className="fixed bottom-[max(1rem,env(safe-area-inset-bottom))] left-4 right-4 sm:left-auto sm:right-6 z-50 animate-in fade-in slide-in-from-bottom-4 duration-200 pointer-events-none" role="status" aria-live="polite" aria-atomic="true">
      <div className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-2xl bg-zinc-900/95 border border-zinc-700/80 text-zinc-100 text-xs font-medium shadow-2xl backdrop-blur-xl">
        <Check className="w-4 h-4 text-emerald-400 shrink-0" />
        <span>{message}</span>
      </div>
    </div>
  );
};
