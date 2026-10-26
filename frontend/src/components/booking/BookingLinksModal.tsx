import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Copy,
  Check,
  ExternalLink,
  AlertCircle,
  Users,
  Sparkles,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import { FormField } from '../ui/FormField';
import { Select } from '../ui/Select';
import { Badge } from '../ui/Badge';
import { Spinner } from '../ui/Spinner';

export interface BookingLinksModalProps {
  driveId: string;
  driveTitle: string;
  candidates: Array<{ id: string; name: string; email?: string; status?: string }>;
  isOpen: boolean;
  onClose: () => void;
}

export interface GeneratedLink {
  candidate_id: string;
  token: string;
  path: string;
}

export interface SkippedCandidate {
  candidate_id: string;
  reason: string;
}

export interface IssueLinksResponse {
  links: GeneratedLink[];
  skipped: SkippedCandidate[];
}

export const BookingLinksModal: React.FC<BookingLinksModalProps> = ({
  driveId,
  driveTitle,
  candidates,
  isOpen,
  onClose,
}) => {
  const [ttlHours, setTtlHours] = useState<number>(48);
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>([]);
  const [result, setResult] = useState<IssueLinksResponse | null>(null);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  const candidateMap = new Map(candidates.map((c) => [c.id, c.name]));

  const issueMutation = useMutation({
    mutationFn: (data: { candidate_ids: string[]; ttl_hours: number }) =>
      apiClient.post<IssueLinksResponse>(`/drives/${driveId}/booking-links`, data),
    onSuccess: (data) => {
      setResult(data);
    },
  });

  const handleSelectAll = () => {
    if (selectedCandidateIds.length === candidates.length) {
      setSelectedCandidateIds([]);
    } else {
      setSelectedCandidateIds(candidates.map((c) => c.id));
    }
  };

  const handleGenerate = () => {
    const ids = selectedCandidateIds.length > 0 ? selectedCandidateIds : candidates.map((c) => c.id);
    issueMutation.mutate({ candidate_ids: ids, ttl_hours: ttlHours });
  };

  const copyToClipboard = (token: string) => {
    const fullUrl = `${window.location.origin}/book/${token}`;
    navigator.clipboard.writeText(fullUrl);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(null), 2500);
  };

  const resetModal = () => {
    setResult(null);
    setSelectedCandidateIds([]);
    onClose();
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={resetModal}
      title="Generate Self-Booking Links"
      maxWidth="lg"
    >
      <div className="space-y-5">
        {!result ? (
          <>
            <p className="text-xs text-slate-400">
              Generate signed, self-booking links for candidates in <span className="text-slate-200 font-semibold">{driveTitle}</span>. Candidates can pick their preferred interview slot from available rooms and panelists.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <FormField label="Link Expiration (TTL)">
                <Select
                  value={ttlHours}
                  onChange={(e) => setTtlHours(Number(e.target.value))}
                >
                  <option value={24}>24 Hours (1 day)</option>
                  <option value={48}>48 Hours (2 days - Recommended)</option>
                  <option value={72}>72 Hours (3 days)</option>
                  <option value={168}>168 Hours (7 days)</option>
                </Select>
              </FormField>

              <div className="flex flex-col justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSelectAll}
                  className="w-full text-slate-300 border-slate-700 hover:bg-slate-800"
                >
                  <Users className="w-3.5 h-3.5 mr-1.5" />
                  {selectedCandidateIds.length === candidates.length
                    ? 'Deselect All'
                    : `Select All Candidates (${candidates.length})`}
                </Button>
              </div>
            </div>

            {/* Candidates Picker List */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Select Target Candidates ({selectedCandidateIds.length || candidates.length} of {candidates.length})
              </label>
              <div className="max-h-60 overflow-y-auto rounded-xl border border-slate-800 divide-y divide-slate-800/60 bg-slate-950/40 p-1">
                {candidates.map((c) => {
                  const isChecked = selectedCandidateIds.includes(c.id);
                  return (
                    <label
                      key={c.id}
                      className="flex items-center justify-between p-2.5 hover:bg-slate-800/40 rounded-lg cursor-pointer transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedCandidateIds([...selectedCandidateIds, c.id]);
                            } else {
                              setSelectedCandidateIds(selectedCandidateIds.filter((id) => id !== c.id));
                            }
                          }}
                          className="rounded border-slate-700 bg-slate-800 text-indigo-600 focus:ring-indigo-500"
                        />
                        <div>
                          <p className="text-xs font-medium text-slate-200">{c.name}</p>
                          {c.email && <p className="text-[11px] text-slate-500">{c.email}</p>}
                        </div>
                      </div>
                      {c.status && (
                        <Badge variant={c.status === 'active' ? 'brand' : 'neutral'} size="sm">
                          {c.status}
                        </Badge>
                      )}
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
              <Button variant="ghost" onClick={resetModal}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleGenerate}
                disabled={issueMutation.isPending || candidates.length === 0}
                className="bg-indigo-600 hover:bg-indigo-500"
              >
                {issueMutation.isPending ? (
                  <>
                    <Spinner size="sm" className="mr-2" />
                    Issuing Links...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-1.5" />
                    Issue Booking Links
                  </>
                )}
              </Button>
            </div>
          </>
        ) : (
          /* Results View */
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
              <h4 className="text-sm font-bold text-emerald-300">
                {result.links.length} Booking Link(s) Generated!
              </h4>
              <p className="text-xs text-emerald-200/80 mt-0.5">
                Share these personalized links with candidates so they can confirm an interview slot.
              </p>
            </div>

            {/* Generated Links List */}
            {result.links.length > 0 && (
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Active Booking Links
                </label>
                <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
                  {result.links.map((link) => {
                    const cName = candidateMap.get(link.candidate_id) || 'Candidate';
                    const fullUrl = `${window.location.origin}/book/${link.token}`;
                    const isCopied = copiedToken === link.token;

                    return (
                      <div
                        key={link.candidate_id}
                        className="p-3 rounded-xl bg-slate-900 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-bold text-slate-200 truncate">{cName}</p>
                          <p className="text-[11px] font-mono text-slate-400 truncate mt-0.5">
                            {fullUrl}
                          </p>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => copyToClipboard(link.token)}
                            className="text-xs py-1 px-2.5 border-slate-700 text-slate-300 hover:bg-slate-800"
                          >
                            {isCopied ? (
                              <>
                                <Check className="w-3.5 h-3.5 text-emerald-400 mr-1" />
                                Copied
                              </>
                            ) : (
                              <>
                                <Copy className="w-3.5 h-3.5 text-slate-400 mr-1" />
                                Copy Link
                              </>
                            )}
                          </Button>
                          <a
                            href={`/book/${link.token}`}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg bg-indigo-600/20 text-indigo-300 hover:bg-indigo-600/30 font-medium transition-colors border border-indigo-500/30"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                            Open
                          </a>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Skipped Candidates List */}
            {result.skipped.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <label className="text-xs font-semibold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5" />
                  Skipped Candidates ({result.skipped.length})
                </label>
                <div className="space-y-1.5">
                  {result.skipped.map((skip, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-between text-xs"
                    >
                      <span className="font-medium text-slate-200">
                        {candidateMap.get(skip.candidate_id) || skip.candidate_id}
                      </span>
                      <span className="text-amber-300 text-[11px]">{skip.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex justify-end pt-3 border-t border-slate-800">
              <Button variant="primary" onClick={resetModal}>
                Done
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};
