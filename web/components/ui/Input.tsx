import {
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";

type FieldChromeProps = {
  id?: string;
  label?: ReactNode;
  hint?: ReactNode;
  error?: string;
  className?: string;
};

const controlBase =
  "w-full rounded-control border bg-canvas px-3 py-2 text-sm text-ink placeholder:text-ink-subtle transition focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:opacity-50";

function controlBorder(hasError: boolean) {
  return hasError
    ? "border-red-500/70 focus:border-red-400 focus:ring-red-500/30"
    : "border-line-strong focus:border-brand focus:ring-brand/30";
}

export interface InputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "id">,
    FieldChromeProps {}

export function Input({
  id,
  label,
  hint,
  error,
  className = "",
  ...rest
}: InputProps) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  const errorId = `${fieldId}-error`;
  const hintId = `${fieldId}-hint`;
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(" ") || undefined;

  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={fieldId} className="block text-xs font-medium text-ink-muted">
          {label}
        </label>
      )}
      <input
        id={fieldId}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
        className={`${controlBase} ${controlBorder(Boolean(error))} ${className}`}
        {...rest}
      />
      {error && (
        <p id={errorId} className="text-xs text-red-400">
          {error}
        </p>
      )}
      {hint && !error && (
        <p id={hintId} className="text-xs text-ink-subtle">
          {hint}
        </p>
      )}
    </div>
  );
}

export interface TextareaProps
  extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id">,
    FieldChromeProps {}

export function Textarea({
  id,
  label,
  hint,
  error,
  className = "",
  ...rest
}: TextareaProps) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  const errorId = `${fieldId}-error`;
  const hintId = `${fieldId}-hint`;
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(" ") || undefined;

  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={fieldId} className="block text-xs font-medium text-ink-muted">
          {label}
        </label>
      )}
      <textarea
        id={fieldId}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
        className={`${controlBase} ${controlBorder(Boolean(error))} min-h-24 ${className}`}
        {...rest}
      />
      {error && (
        <p id={errorId} className="text-xs text-red-400">
          {error}
        </p>
      )}
      {hint && !error && (
        <p id={hintId} className="text-xs text-ink-subtle">
          {hint}
        </p>
      )}
    </div>
  );
}

export interface SelectProps
  extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "id">,
    FieldChromeProps {
  children: ReactNode;
}

export function Select({
  id,
  label,
  hint,
  error,
  className = "",
  children,
  ...rest
}: SelectProps) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  const errorId = `${fieldId}-error`;
  const describedBy = error ? errorId : undefined;

  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={fieldId} className="block text-xs font-medium text-ink-muted">
          {label}
        </label>
      )}
      <select
        id={fieldId}
        aria-invalid={Boolean(error)}
        aria-describedby={describedBy}
        className={`${controlBase} ${controlBorder(Boolean(error))} ${className}`}
        {...rest}
      >
        {children}
      </select>
      {error && (
        <p id={errorId} className="text-xs text-red-400">
          {error}
        </p>
      )}
      {hint && !error && <p className="text-xs text-ink-subtle">{hint}</p>}
    </div>
  );
}

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "id"> {
  id?: string;
  label: ReactNode;
  error?: string;
}

export function Checkbox({ id, label, error, className = "", ...rest }: CheckboxProps) {
  const autoId = useId();
  const fieldId = id ?? autoId;
  const errorId = `${fieldId}-error`;

  return (
    <div className="space-y-1">
      <label htmlFor={fieldId} className="flex cursor-pointer items-start gap-2.5 text-sm text-ink-muted">
        <input
          id={fieldId}
          type="checkbox"
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errorId : undefined}
          className={`mt-0.5 h-4 w-4 shrink-0 rounded border-line-strong accent-brand ${className}`}
          {...rest}
        />
        <span>{label}</span>
      </label>
      {error && (
        <p id={errorId} className="text-xs text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}
