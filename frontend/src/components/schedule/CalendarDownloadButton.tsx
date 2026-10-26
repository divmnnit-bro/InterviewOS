import React, { useState } from 'react';
import { Download } from 'lucide-react';
import { downloadInterviewCalendar } from '@/api/client';
import { Button, ButtonProps } from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';

interface CalendarDownloadButtonProps {
  interviewId: string;
  label?: string;
  className?: string;
  variant?: ButtonProps['variant'];
  size?: ButtonProps['size'];
  onClick?: React.MouseEventHandler<HTMLButtonElement>;
}

export const CalendarDownloadButton: React.FC<CalendarDownloadButtonProps> = ({
  interviewId,
  label = '.ics',
  className,
  variant = 'ghost',
  size = 'sm',
  onClick,
}) => {
  const [isDownloading, setIsDownloading] = useState(false);
  const toast = useToast();

  const handleDownload = async (event: React.MouseEvent<HTMLButtonElement>) => {
    onClick?.(event);
    setIsDownloading(true);
    try {
      await downloadInterviewCalendar(interviewId);
      toast.success('Calendar file downloaded');
    } catch (error) {
      toast.error('Calendar download failed', error instanceof Error ? error.message : 'Please try again.');
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <Button
      type="button"
      variant={variant}
      size={size}
      className={className}
      isLoading={isDownloading}
      onClick={handleDownload}
      aria-label={`Download calendar for interview ${interviewId}`}
      leftIcon={<Download className="w-3.5 h-3.5" />}
    >
      {label}
    </Button>
  );
};
