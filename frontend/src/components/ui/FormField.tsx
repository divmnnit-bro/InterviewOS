import React from 'react';
import clsx from 'clsx';
import { AlertCircle } from 'lucide-react';

export interface FormFieldProps {
  label?: string;
  htmlFor?: string;
  error?: string | null;
  hint?: string;
  required?: boolean;
  className?: string;
  children: React.ReactNode;
}

export const FormField: React.FC<FormFieldProps> = ({
  label,
  htmlFor,
  error,
  hint,
  required,
  className,
  children,
}) => {
  return (
    <div className={clsx('flex flex-col space-y-1.5 text-left w-full', className)}>
      {label && (
        <label
          htmlFor={htmlFor}
          className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center justify-between"
        >
          <span>
            {label}
            {required && <span className="text-rose-400 ml-1 font-bold">*</span>}
          </span>
        </label>
      )}
      {children}
      {error ? (
        <p className="text-xs text-rose-400 flex items-center gap-1 font-medium mt-1 animate-fadeIn">
          <AlertCircle className="w-3.5 h-3.5 shrink-0" />
          <span>{error}</span>
        </p>
      ) : hint ? (
        <p className="text-xs text-slate-500 mt-0.5">{hint}</p>
      ) : null}
    </div>
  );
};
