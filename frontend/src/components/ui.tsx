import {
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  forwardRef,
} from 'react';

function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md';

const buttonVariants: Record<ButtonVariant, string> = {
  primary: 'border-action bg-action text-on-action hover:bg-action-hover-hover',
  secondary: 'border-border-strong bg-surface text-primary hover:bg-surface-raised',
  ghost: 'border-transparent bg-transparent text-secondary hover:bg-surface-raised hover:text-primary',
  danger: 'border-danger-border bg-danger text-on-action hover:brightness-90',
};

const buttonSizes: Record<ButtonSize, string> = {
  sm: 'min-h-11 px-3 text-xs',
  md: 'min-h-11 px-4 text-sm',
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = 'secondary', size = 'md', type = 'button', ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-[10px] border font-semibold transition-colors disabled:pointer-events-none disabled:opacity-50',
        buttonVariants[variant],
        buttonSizes[size],
        className,
      )}
      {...props}
    />
  );
});

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  variant?: Extract<ButtonVariant, 'secondary' | 'ghost' | 'danger'>;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, className, variant = 'ghost', type = 'button', ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      aria-label={label}
      className={cx(
        'inline-flex min-h-11 min-w-11 items-center justify-center rounded-[10px] border transition-colors disabled:pointer-events-none disabled:opacity-50',
        buttonVariants[variant],
        className,
      )}
      {...props}
    />
  );
});

export interface SurfaceProps extends HTMLAttributes<HTMLDivElement> {
  elevation?: 'base' | 'raised';
}

export const Surface = forwardRef<HTMLDivElement, SurfaceProps>(function Surface(
  { className, elevation = 'base', ...props },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cx(
        'rounded-[14px] border border-border-subtle',
        elevation === 'raised' ? 'bg-surface-raised' : 'bg-surface',
        className,
      )}
      {...props}
    />
  );
});

export const DialogSurface = forwardRef<HTMLDivElement, SurfaceProps>(function DialogSurface(
  { className, ...props },
  ref,
) {
  return (
    <Surface
      ref={ref}
      role="dialog"
      aria-modal="true"
      className={cx('ui-surface-enter shadow-2xl', className)}
      {...props}
    />
  );
});

export function Badge({
  tone = 'neutral',
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: 'neutral' | 'accent' | 'positive' | 'warning' | 'danger' }) {
  const tones = {
    neutral: 'badge-neutral',
    accent: 'badge-accent',
    positive: 'border-positive-border bg-positive-soft text-positive',
    warning: 'border-warning-border bg-warning-soft text-warning',
    danger: 'border-danger-border bg-danger-soft text-danger',
  };
  return <span className={cx('inline-flex items-center rounded-full border px-2 py-1 text-xs font-medium', tones[tone], className)} {...props} />;
}

export interface SegmentOption<T extends string> {
  value: T;
  label: string;
  icon?: ReactNode;
}

export function SegmentedControl<T extends string>({
  label,
  value,
  options,
  onChange,
  className,
}: {
  label: string;
  value: T;
  options: readonly SegmentOption<T>[];
  onChange: (value: T) => void;
  className?: string;
}) {
  return (
    <div className={cx('inline-flex items-center rounded-[10px] border border-border-subtle bg-surface-raised p-1', className)} aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={cx(
            'inline-flex min-h-11 items-center gap-1.5 rounded-lg px-2.5 text-xs font-medium transition-colors',
            value === option.value ? 'bg-action text-on-action' : 'text-secondary hover:bg-surface-selected hover:text-primary',
          )}
          aria-pressed={value === option.value}
        >
          {option.icon}
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function MenuItem({ className, ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      role="menuitem"
      className={cx('flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm text-secondary transition-colors hover:bg-surface-raised hover:text-primary', className)}
      {...props}
    />
  );
}

export function EmptyState({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cx('ui-panel px-5 py-12 text-center text-secondary', className)} {...props} />;
}

export interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string;
  error?: string;
}

export const Field = forwardRef<HTMLInputElement, FieldProps>(function Field(
  { id, label, hint, error, className, ...props },
  ref,
) {
  const fieldId = id ?? `field-${props.name}`;
  const descriptionId = hint || error ? `${fieldId}-description` : undefined;
  return (
    <label htmlFor={fieldId} className="block">
      <span className="ui-label mb-1.5 block">{label}</span>
      <input
        ref={ref}
        id={fieldId}
        aria-invalid={Boolean(error)}
        aria-describedby={descriptionId}
        className={cx('ui-control w-full px-3 text-sm placeholder:text-muted', className)}
        {...props}
      />
      {(error || hint) && (
        <span id={descriptionId} className={cx('mt-1.5 block text-xs', error ? 'text-danger' : 'text-muted')}>
          {error ?? hint}
        </span>
      )}
    </label>
  );
});

export function SectionHeading({ children, className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2 className={cx('text-sm font-semibold tracking-tight text-primary', className)} {...props}>
      {children}
    </h2>
  );
}

export interface StatusMessageProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  tone?: 'neutral' | 'positive' | 'warning' | 'danger';
}

export function StatusMessage({ children, tone = 'neutral', className, ...props }: StatusMessageProps) {
  const tones = {
    neutral: 'border-border-subtle bg-surface-raised text-secondary',
    positive: 'border-positive-border bg-positive-soft text-positive',
    warning: 'border-warning-border bg-warning-soft text-warning',
    danger: 'border-danger-border bg-danger-soft text-danger',
  };
  return <div className={cx('rounded-[10px] border px-3 py-2.5 text-sm', tones[tone], className)} {...props}>{children}</div>;
}
