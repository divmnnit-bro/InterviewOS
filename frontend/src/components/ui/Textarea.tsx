import React, { forwardRef } from 'react';
import clsx from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, rows = 3, ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        rows={rows}
        className={twMerge(
          clsx(
            'w-full rounded-lg bg-surface-elevated/70 border text-slate-100 placeholder-slate-500 text-sm py-2 px-3 transition-colors duration-150 resize-y',
            'focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500',
            'disabled:opacity-50 disabled:bg-surface-elevated/30 disabled:cursor-not-allowed',
            error ? 'border-rose-500/80 focus:border-rose-500 focus:ring-rose-500/40' : 'border-surface-border'
          ),
          className
        )}
        {...props}
      />
    );
  }
);

Textarea.displayName = 'Textarea';
