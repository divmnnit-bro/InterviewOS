import React from 'react';
import clsx from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'elevated' | 'glass';
  glow?: boolean;
}

export const Card: React.FC<CardProps> = ({
  className,
  variant = 'default',
  glow = false,
  children,
  ...props
}) => {
  const variants = {
    default: 'bg-surface-card border border-surface-border',
    elevated: 'bg-surface-elevated border border-surface-border shadow-xl',
    glass: 'bg-glass border border-surface-border shadow-2xl',
  };

  return (
    <div
      className={twMerge(
        clsx(
          'rounded-xl p-5 text-slate-100 transition-all duration-200',
          variants[variant],
          glow && 'glow-border',
          className
        )
      )}
      {...props}
    >
      {children}
    </div>
  );
};

export const CardHeader: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => (
  <div className={twMerge('flex items-center justify-between pb-4 border-b border-surface-border/60 mb-4', className)} {...props}>
    {children}
  </div>
);

export const CardTitle: React.FC<React.HTMLAttributes<HTMLHeadingElement>> = ({
  className,
  children,
  ...props
}) => (
  <h3 className={twMerge('text-base font-semibold text-slate-100 tracking-tight', className)} {...props}>
    {children}
  </h3>
);

export const CardDescription: React.FC<React.HTMLAttributes<HTMLParagraphElement>> = ({
  className,
  children,
  ...props
}) => (
  <p className={twMerge('text-xs text-slate-400 mt-0.5', className)} {...props}>
    {children}
  </p>
);

export const CardContent: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => <div className={twMerge('', className)} {...props}>{children}</div>;

export const CardFooter: React.FC<React.HTMLAttributes<HTMLDivElement>> = ({
  className,
  children,
  ...props
}) => (
  <div className={twMerge('flex items-center justify-between pt-4 border-t border-surface-border/60 mt-4', className)} {...props}>
    {children}
  </div>
);
