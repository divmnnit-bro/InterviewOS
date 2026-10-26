import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Sparkles,
  BookOpen,
  FileText,
  UserCheck,
  MessageSquare,
  Copy,
  Check,
  AlertCircle,
  ChevronRight,
  Code2,
  Cpu,
  BrainCircuit,
  ArrowRight,
  Send,
  RefreshCw,
} from 'lucide-react';
import { apiClient } from '@/api/client';
import {
  InterviewKitResponse,
  DriveBriefResponse,
  CandidateSummaryResponse,
  AskRecruitmentDataResponse,
} from '@/types/ai';
import { RecruitmentDrive } from '@/types/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';

export const AICopilotPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'kit' | 'brief' | 'candidate' | 'ask'>('kit');

  // Drives query for dropdowns
  const { data: drives = [] } = useQuery<RecruitmentDrive[]>({
    queryKey: ['drives'],
    queryFn: () => apiClient.get<RecruitmentDrive[]>('/drives'),
  });

  // State for Interview Kit
  const [kitDriveId, setKitDriveId] = useState<string>('');
  const [kitTopic, setKitTopic] = useState<string>('Distributed Systems & Concurrency');
  const [kitDifficulty, setKitDifficulty] = useState<'beginner' | 'intermediate' | 'advanced'>('intermediate');
  const [kitJobDesc, setKitJobDesc] = useState<string>('Senior Backend Infrastructure Engineer');
  const [kitSkills, setKitSkills] = useState<string>('Python, PostgreSQL, Distributed Systems, Redis');
  const [copiedSection, setCopiedSection] = useState<string | null>(null);
  const [kitDraft, setKitDraft] = useState<InterviewKitResponse | null>(null);

  // State for Drive Brief
  const [briefDriveId, setBriefDriveId] = useState<string>('');

  // State for Candidate Summary
  const [candDriveId, setCandDriveId] = useState<string>('');
  const [candidateId, setCandidateId] = useState<string>('');

  // Candidates for selected drive
  const { data: candidates = [] } = useQuery<Array<{ candidate_id: string; candidate_name?: string }>>({
    queryKey: ['drive-candidates', candDriveId],
    queryFn: () => apiClient.get(`/drives/${candDriveId}/candidates`),
    enabled: Boolean(candDriveId),
  });

  // State for Ask Copilot
  const [askQuery, setAskQuery] = useState<string>('');

  // Auto-select first drive if available
  React.useEffect(() => {
    if (drives.length > 0) {
      if (!kitDriveId) setKitDriveId(drives[0].id);
      if (!briefDriveId) setBriefDriveId(drives[0].id);
      if (!candDriveId) setCandDriveId(drives[0].id);
    }
  }, [drives]);

  // Mutations
  const kitMutation = useMutation<InterviewKitResponse>({
    onMutate: () => setKitDraft(null),
    onSuccess: (data) => setKitDraft(data),
    mutationFn: () =>
      apiClient.post<InterviewKitResponse>('/ai/interview-kit', {
        drive_id: kitDriveId || undefined,
        topic: kitTopic,
        difficulty: kitDifficulty,
        job_description: kitJobDesc,
        required_skills: kitSkills.split(',').map((s) => s.trim()).filter(Boolean),
      }),
  });

  const saveKitMutation = useMutation<InterviewKitResponse, Error, void>({
    mutationFn: () => {
      const draft = kitDraft ?? kitMutation.data;
      if (!draft?.kit_id) throw new Error('Generate and load a saved kit before saving edits.');
      return apiClient.put<InterviewKitResponse>(`/ai/interview-kits/${draft.kit_id}`, {
        topic: draft.topic,
        difficulty: draft.difficulty,
        coding_questions: draft.coding_questions,
        system_design_scenarios: draft.system_design_scenarios,
        behavioral_questions: draft.behavioral_questions,
        multiple_choice_questions: draft.multiple_choice_questions,
        competencies_to_assess: draft.competencies_to_assess,
        rubric_template: draft.rubric_template,
      });
    },
    onSuccess: (data) => setKitDraft(data),
  });

  const updateKitDraft = (update: (current: InterviewKitResponse) => InterviewKitResponse) => {
    const current = kitDraft ?? kitMutation.data;
    if (current) setKitDraft(update(current));
  };

  const briefMutation = useMutation<DriveBriefResponse>({
    mutationFn: () =>
      apiClient.post<DriveBriefResponse>('/ai/drive-brief', {
        drive_id: briefDriveId,
      }),
  });

  const candidateMutation = useMutation<CandidateSummaryResponse>({
    mutationFn: () =>
      apiClient.post<CandidateSummaryResponse>('/ai/candidate-summary', {
        drive_id: candDriveId,
        candidate_id: candidateId,
      }),
  });

  const askMutation = useMutation<AskRecruitmentDataResponse>({
    mutationFn: () =>
      apiClient.post<AskRecruitmentDataResponse>('/ai/ask', {
        question: askQuery,
      }),
  });

  const handleCopy = (text: string, sectionId: string) => {
    navigator.clipboard.writeText(text);
    setCopiedSection(sectionId);
    setTimeout(() => setCopiedSection(null), 2000);
  };

  const kit = kitDraft ?? kitMutation.data;

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-surface-border pb-6">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 bg-indigo-500/10 border border-indigo-500/20 rounded-xl text-indigo-400">
              <Sparkles className="w-6 h-6 animate-pulse" />
            </div>
            <h1 className="text-2xl font-bold text-slate-100">AI Recruitment Copilot</h1>
            <Badge variant="outline" className="text-xs bg-indigo-500/10 text-indigo-300 border-indigo-500/30">
              Intelligence Engine
            </Badge>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Grounded AI intelligence for interview kit generation, drive operations briefing, candidate synthesis, and recruitment database queries.
          </p>
          <p className="text-xs text-slate-500 mt-1">External providers receive the role topic and skill tags only; raw job-description text stays local.</p>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex border-b border-surface-border gap-2 overflow-x-auto">
        <button
          onClick={() => setActiveTab('kit')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
            activeTab === 'kit'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <BookOpen className="w-4 h-4" />
          Interview Kit Studio
        </button>
        <button
          onClick={() => setActiveTab('brief')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
            activeTab === 'brief'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <FileText className="w-4 h-4" />
          Drive Briefing & Risks
        </button>
        <button
          onClick={() => setActiveTab('candidate')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
            activeTab === 'candidate'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <UserCheck className="w-4 h-4" />
          Candidate Synthesis
        </button>
        <button
          onClick={() => setActiveTab('ask')}
          className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
            activeTab === 'ask'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          Ask Copilot (Q&A)
        </button>
      </div>

      {/* TAB 1: Interview Kit Studio */}
      {activeTab === 'kit' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Controls */}
          <div className="space-y-4 lg:col-span-1">
            <Card className="bg-surface-card border-surface-border">
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <BrainCircuit className="w-4 h-4 text-indigo-400" />
                  Generation Parameters
                </CardTitle>
                <CardDescription>Configure interview kit criteria</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Recruitment Drive</label>
                  <Select
                    value={kitDriveId}
                    onChange={(e) => setKitDriveId(e.target.value)}
                    options={drives.map((d) => ({ value: d.id, label: d.title }))}
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Interview Topic / Domain</label>
                  <Input
                    value={kitTopic}
                    onChange={(e) => setKitTopic(e.target.value)}
                    placeholder="e.g. Algorithms, Data Systems, Frontend"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Target Difficulty</label>
                  <div className="grid grid-cols-3 gap-2">
                    {(['beginner', 'intermediate', 'advanced'] as const).map((diff) => (
                      <button
                        key={diff}
                        type="button"
                        onClick={() => setKitDifficulty(diff)}
                        className={`py-1.5 text-xs font-medium rounded-lg border capitalize transition-all ${
                          kitDifficulty === diff
                            ? 'bg-indigo-600 text-white border-indigo-500 shadow-sm'
                            : 'bg-slate-900/60 text-slate-400 border-surface-border hover:bg-slate-800'
                        }`}
                      >
                        {diff}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Job Description / Role</label>
                  <Input
                    value={kitJobDesc}
                    onChange={(e) => setKitJobDesc(e.target.value)}
                    placeholder="e.g. Senior Backend Engineer"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Required Skills (comma separated)</label>
                  <Input
                    value={kitSkills}
                    onChange={(e) => setKitSkills(e.target.value)}
                    placeholder="Python, SQL, System Architecture"
                  />
                </div>

                <Button
                  onClick={() => kitMutation.mutate()}
                  disabled={kitMutation.isPending}
                  className="w-full bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center gap-2 mt-4"
                >
                  {kitMutation.isPending ? <Spinner size="sm" /> : <Sparkles className="w-4 h-4" />}
                  Generate Interview Kit
                </Button>
              </CardContent>
            </Card>
          </div>

          {/* Results Viewer */}
          <div className="lg:col-span-2 space-y-6">
            {kitMutation.isPending && (
              <Card className="bg-surface-card border-surface-border p-12 text-center">
                <Spinner size="lg" className="mx-auto mb-4 text-indigo-400" />
                <h3 className="text-lg font-semibold text-slate-200">Generating Structured Interview Kit</h3>
                <p className="text-sm text-slate-400 mt-1">
                  Synthesizing coding problems, system design constraints, behavioral rubrics, and evaluation scales...
                </p>
              </Card>
            )}

            {kitMutation.isError && (
              <Card className="bg-rose-950/20 border-rose-800/40 p-6 text-rose-300 flex items-start gap-3">
                <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold">Generation Failed</p>
                  <p className="text-sm text-rose-400 mt-1">{(kitMutation.error as any)?.message || 'An error occurred'}</p>
                </div>
              </Card>
            )}

            {!kitMutation.data && !kitMutation.isPending && !kitMutation.isError && (
              <Card className="bg-surface-card border-surface-border p-12 text-center">
                <BookOpen className="w-12 h-12 text-slate-600 mx-auto mb-3" />
                <h3 className="text-lg font-semibold text-slate-300">Ready to Generate Interview Kit</h3>
                <p className="text-sm text-slate-400 max-w-md mx-auto mt-1">
                  Select your drive, difficulty, and role parameters on the left to produce standardized coding questions, architecture scenarios, and scoring rubrics.
                </p>
              </Card>
            )}

            {kit && (
              <div className="space-y-6">
                {/* Meta Banner */}
                <div className="flex items-center justify-between p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-xl text-sm">
                  <div className="flex items-center gap-2 text-indigo-300">
                    <Sparkles className="w-4 h-4 text-indigo-400" />
                    <span>Provider: <strong className="text-indigo-200">{kit.provider_used || 'Deterministic Engine'}</strong></span>
                    <span className="text-slate-500">•</span>
                    <span>Difficulty: <strong className="capitalize text-indigo-200">{kit.difficulty}</strong></span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button variant="primary" size="sm" onClick={() => saveKitMutation.mutate()} disabled={!kit.kit_id || saveKitMutation.isPending} isLoading={saveKitMutation.isPending} className="text-xs">Save reviewed draft</Button>
                    <Button variant="outline" size="sm" onClick={() => handleCopy(JSON.stringify(kit, null, 2), 'all')} className="text-xs">
                      {copiedSection === 'all' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      Copy Full Kit JSON
                    </Button>
                  </div>
                </div>
                <p className="text-xs text-amber-300/90">Draft for coordinator review. Generated questions and answer keys should be checked before use; this action saves the reviewed draft and does not publish it.</p>
                {saveKitMutation.isError && <p role="alert" className="text-xs text-rose-300">Could not save draft: {saveKitMutation.error.message}</p>}

                {/* Coding Questions */}
                <Card className="bg-surface-card border-surface-border">
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Code2 className="w-4 h-4 text-emerald-400" />
                      Coding & Algorithmic Challenges ({kit.coding_questions.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {kit.coding_questions.map((cq, idx) => (
                      <div key={idx} className="p-4 bg-slate-900/60 border border-surface-border rounded-xl space-y-3">
                        <div className="flex items-center justify-between">
                          <h4 className="font-semibold text-slate-100">{cq.title}</h4>
                          <Badge variant="outline" className="capitalize text-xs">
                            {cq.difficulty}
                          </Badge>
                        </div>
                        <textarea aria-label={`Edit coding problem ${idx + 1}`} value={cq.description} onChange={(e) => updateKitDraft((current) => ({ ...current, coding_questions: current.coding_questions.map((question, questionIndex) => questionIndex === idx ? { ...question, description: e.target.value } : question) }))} className="w-full min-h-24 rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm text-slate-300" />
                        {cq.competencies_to_assess.length > 0 && <p className="text-xs text-emerald-300">Competencies: {cq.competencies_to_assess.join(', ')}</p>}
                        {cq.follow_up_questions.length > 0 && <div><span className="text-xs font-semibold text-slate-400">Follow-up questions:</span><ul className="mt-1 list-disc list-inside text-xs text-slate-300">{cq.follow_up_questions.map((question, i) => <li key={i}>{question}</li>)}</ul></div>}

                        {/* Constraints & Concepts */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                          <div>
                            <span className="text-xs font-semibold text-slate-400 block mb-1">Constraints:</span>
                            <ul className="list-disc list-inside text-xs text-slate-300 space-y-0.5">
                              {cq.constraints.map((c, i) => (
                                <li key={i}>{c}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <span className="text-xs font-semibold text-slate-400 block mb-1">Expected Concepts:</span>
                            <div className="flex flex-wrap gap-1.5">
                              {cq.expected_concepts.map((concept, i) => (
                                <Badge key={i} variant="outline" className="text-xs bg-slate-800 text-slate-300">
                                  {concept}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        </div>

                        {/* Sample I/O */}
                        {cq.sample_inputs_outputs.length > 0 && (
                          <div className="pt-2">
                            <span className="text-xs font-semibold text-slate-400 block mb-1">Sample Cases:</span>
                            <div className="space-y-1.5">
                              {cq.sample_inputs_outputs.map((sample, sIdx) => (
                                <div key={sIdx} className="p-2 bg-slate-950 font-mono text-xs rounded border border-surface-border text-slate-300">
                                  <div><span className="text-indigo-400">Input:</span> {sample.input}</div>
                                  <div><span className="text-emerald-400">Output:</span> {sample.output}</div>
                                  {sample.explanation && <div className="text-slate-500 mt-0.5">{sample.explanation}</div>}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </CardContent>
                </Card>

                <Card className="bg-surface-card border-surface-border">
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2"><BrainCircuit className="w-4 h-4 text-amber-400" />Multiple-choice assessment ({kit.multiple_choice_questions.length})</CardTitle>
                    <CardDescription>Answer keys and explanations are visible to coordinators. Edit the draft before using it.</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-5">
                    <div>
                      <label className="text-xs font-semibold text-slate-400 block mb-1">Competencies covered</label>
                      <Input value={kit.competencies_to_assess.join(', ')} onChange={(e) => updateKitDraft((current) => ({ ...current, competencies_to_assess: e.target.value.split(',').map((item) => item.trim()).filter(Boolean) }))} aria-label="Edit competency coverage" />
                    </div>
                    {kit.multiple_choice_questions.map((question, questionIndex) => (
                      <div key={questionIndex} className="p-4 bg-slate-900/60 border border-surface-border rounded-xl space-y-3">
                        <div className="flex flex-wrap items-center justify-between gap-2"><Badge variant="outline">{question.competency}</Badge><Badge variant="outline" className="capitalize">{question.difficulty}</Badge></div>
                        <Input aria-label={`Edit MCQ ${questionIndex + 1}`} value={question.question} onChange={(e) => updateKitDraft((current) => ({ ...current, multiple_choice_questions: current.multiple_choice_questions.map((item, index) => index === questionIndex ? { ...item, question: e.target.value } : item) }))} />
                        <div className="space-y-2">{question.options.map((option, optionIndex) => <div key={optionIndex} className="flex items-center gap-2"><Input aria-label={`Edit MCQ ${questionIndex + 1} option ${optionIndex + 1}`} value={option} onChange={(e) => updateKitDraft((current) => ({ ...current, multiple_choice_questions: current.multiple_choice_questions.map((item, index) => index === questionIndex ? { ...item, options: item.options.map((choice, choiceIndex) => choiceIndex === optionIndex ? e.target.value : choice) } : item) }))} /><span className={`text-[10px] shrink-0 ${question.correct_answer_index === optionIndex ? 'text-emerald-400' : 'text-slate-500'}`}>{question.correct_answer_index === optionIndex ? 'Answer key' : ''}</span></div>)}</div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3"><label className="text-xs text-slate-400">Correct answer<select aria-label={`Select answer key for MCQ ${questionIndex + 1}`} value={question.correct_answer_index} onChange={(e) => updateKitDraft((current) => ({ ...current, multiple_choice_questions: current.multiple_choice_questions.map((item, index) => index === questionIndex ? { ...item, correct_answer_index: Number(e.target.value) } : item) }))} className="mt-1 w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200">{question.options.map((_, optionIndex) => <option key={optionIndex} value={optionIndex}>Option {optionIndex + 1}</option>)}</select></label><label className="text-xs text-slate-400">Explanation<Input value={question.explanation} onChange={(e) => updateKitDraft((current) => ({ ...current, multiple_choice_questions: current.multiple_choice_questions.map((item, index) => index === questionIndex ? { ...item, explanation: e.target.value } : item) }))} className="mt-1" /></label></div>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                {/* System Design Scenarios */}
                <Card className="bg-surface-card border-surface-border">
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <Cpu className="w-4 h-4 text-sky-400" />
                      System Architecture Scenarios ({kit.system_design_scenarios.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-6">
                    {kit.system_design_scenarios.map((sd, idx) => (
                      <div key={idx} className="p-4 bg-slate-900/60 border border-surface-border rounded-xl space-y-3">
                        <h4 className="font-semibold text-slate-100">{sd.title}</h4>
                        <p className="text-sm text-slate-300">{sd.problem_statement}</p>
                        {sd.competencies_to_assess.length > 0 && <p className="text-xs text-sky-300">Competencies: {sd.competencies_to_assess.join(', ')}</p>}
                        {sd.follow_up_questions.length > 0 && <div><span className="text-xs font-semibold text-slate-400">Follow-up questions:</span><ul className="mt-1 list-disc list-inside text-xs text-slate-300">{sd.follow_up_questions.map((question, i) => <li key={i}>{question}</li>)}</ul></div>}

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                          <div>
                            <span className="text-xs font-semibold text-slate-400 block mb-1">Functional Reqs:</span>
                            <ul className="list-disc list-inside text-xs text-slate-300 space-y-0.5">
                              {sd.functional_requirements.map((r, i) => (
                                <li key={i}>{r}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <span className="text-xs font-semibold text-slate-400 block mb-1">Non-Functional & Scale:</span>
                            <ul className="list-disc list-inside text-xs text-slate-300 space-y-0.5">
                              {sd.non_functional_requirements.concat(sd.scalability_concerns).map((r, i) => (
                                <li key={i}>{r}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>

                {/* Behavioral Questions */}
                <Card className="bg-surface-card border-surface-border">
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <UserCheck className="w-4 h-4 text-amber-400" />
                      Behavioral & Competency Questions ({kit.behavioral_questions.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {kit.behavioral_questions.map((bq, idx) => (
                      <div key={idx} className="p-4 bg-slate-900/60 border border-surface-border rounded-xl space-y-2">
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-semibold text-slate-200">"{bq.question}"</p>
                          <Badge variant="outline" className="text-xs bg-amber-500/10 text-amber-300 border-amber-500/30">
                            {bq.competency}
                          </Badge>
                        </div>
                        <p className="text-xs text-slate-400">{bq.situation_guidance}</p>
                        <p className="text-xs text-slate-300"><strong className="text-slate-400">Scoring guidance:</strong> {bq.evaluation_rubric}</p>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1 text-xs">
                          <div>
                            <span className="font-semibold text-emerald-400 block mb-0.5">Expected Indicators:</span>
                            <ul className="list-disc list-inside text-slate-300 space-y-0.5">
                              {bq.expected_indicators.map((ind, i) => (
                                <li key={i}>{ind}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <span className="font-semibold text-rose-400 block mb-0.5">Red Flags:</span>
                            <ul className="list-disc list-inside text-slate-300 space-y-0.5">
                              {bq.red_flags.map((rf, i) => (
                                <li key={i}>{rf}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                        {bq.follow_up_questions.length > 0 && <div><span className="font-semibold text-indigo-300 text-xs">Follow-up questions:</span><ul className="mt-1 list-disc list-inside text-xs text-slate-300">{bq.follow_up_questions.map((question, i) => <li key={i}>{question}</li>)}</ul></div>}
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: Drive Briefing & Risks */}
      {activeTab === 'brief' && (
        <div className="space-y-6">
          <Card className="bg-surface-card border-surface-border">
            <CardContent className="p-6">
              <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                <div className="flex-1">
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Select Drive to Analyze</label>
                  <Select
                    value={briefDriveId}
                    onChange={(e) => setBriefDriveId(e.target.value)}
                    options={drives.map((d) => ({ value: d.id, label: `${d.title} (${d.status})` }))}
                  />
                </div>
                <div className="sm:pt-5">
                  <Button
                    onClick={() => briefMutation.mutate()}
                    disabled={briefMutation.isPending || !briefDriveId}
                    className="bg-indigo-600 hover:bg-indigo-500 text-white flex items-center gap-2"
                  >
                    {briefMutation.isPending ? <Spinner size="sm" /> : <RefreshCw className="w-4 h-4" />}
                    Generate Coordinator Briefing
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {briefMutation.isPending && (
            <div className="p-12 text-center">
              <Spinner size="lg" className="mx-auto mb-4 text-indigo-400" />
              <p className="text-slate-300 font-medium">Aggregating drive state and computing operational risks...</p>
            </div>
          )}

          {briefMutation.data && (
            <div className="space-y-6">
              {/* Executive Summary */}
              <Card className="bg-gradient-to-r from-indigo-950/40 via-surface-card to-surface-card border-indigo-500/30">
                <CardHeader>
                  <CardTitle className="text-lg flex items-center justify-between">
                    <span className="flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-indigo-400" />
                      Executive Operations Briefing: {briefMutation.data.drive_title}
                    </span>
                    <Badge variant="outline" className="capitalize text-xs bg-indigo-500/10 text-indigo-300 border-indigo-500/30">
                      {briefMutation.data.drive_status}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-slate-200 leading-relaxed whitespace-pre-line">
                    {briefMutation.data.executive_summary}
                  </p>
                  <p className="mt-3 text-xs text-slate-400">
                    {briefMutation.data.is_ai_generated
                      ? `AI summary · ${briefMutation.data.provider_used}`
                      : 'Calculated summary · rule-based'}
                  </p>
                </CardContent>
              </Card>

              {/* Metrics Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="bg-surface-card border-surface-border p-4">
                  <p className="text-xs text-slate-400">Total Enrolled</p>
                  <p className="text-2xl font-bold text-slate-100 mt-1">{briefMutation.data.candidate_counts.total_enrolled}</p>
                </Card>
                <Card className="bg-surface-card border-surface-border p-4">
                  <p className="text-xs text-slate-400">Active in Pipeline</p>
                  <p className="text-2xl font-bold text-indigo-400 mt-1">{briefMutation.data.candidate_counts.active_in_pipeline}</p>
                </Card>
                <Card className="bg-surface-card border-surface-border p-4">
                  <p className="text-xs text-slate-400">Selected</p>
                  <p className="text-2xl font-bold text-emerald-400 mt-1">{briefMutation.data.candidate_counts.selected}</p>
                </Card>
                <Card className="bg-surface-card border-surface-border p-4">
                  <p className="text-xs text-slate-400">Missing Feedback</p>
                  <p className="text-2xl font-bold text-amber-400 mt-1">{briefMutation.data.missing_feedback.length}</p>
                </Card>
              </div>

              {/* Risks & Pending Actions */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="bg-surface-card border-surface-border">
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2 text-amber-400">
                      <AlertCircle className="w-4 h-4" />
                      Scheduling Conflicts & Operational Risks
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2 text-sm text-slate-300">
                      {briefMutation.data.scheduling_conflicts_and_risks.map((risk, i) => (
                        <li key={i} className="flex items-start gap-2 p-2 rounded bg-amber-950/20 border border-amber-800/30">
                          <span className="text-amber-400 font-bold">•</span>
                          {risk}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>

                <Card className="bg-surface-card border-surface-border">
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2 text-indigo-400">
                      <ChevronRight className="w-4 h-4" />
                      Recommended Coordinator Actions
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2 text-sm text-slate-300">
                      {briefMutation.data.pending_actions.map((act, i) => (
                        <li key={i} className="flex items-start gap-2 p-2 rounded bg-indigo-950/20 border border-indigo-800/30">
                          <span className="text-indigo-400 font-bold">✓</span>
                          {act}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: Candidate AI Synthesis */}
      {activeTab === 'candidate' && (
        <div className="space-y-6">
          <Card className="bg-surface-card border-surface-border">
            <CardContent className="p-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Recruitment Drive</label>
                  <Select
                    value={candDriveId}
                    onChange={(e) => {
                      setCandDriveId(e.target.value);
                      setCandidateId('');
                    }}
                    options={drives.map((d) => ({ value: d.id, label: d.title }))}
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Enrolled Candidate</label>
                  <div className="flex gap-2">
                    <Select
                      value={candidateId}
                      onChange={(e) => setCandidateId(e.target.value)}
                      options={candidates.map((c) => ({
                        value: c.candidate_id,
                        label: c.candidate_name || c.candidate_id.substring(0, 8),
                      }))}
                      className="flex-1"
                    />
                    <Button
                      onClick={() => candidateMutation.mutate()}
                      disabled={candidateMutation.isPending || !candidateId}
                      className="bg-indigo-600 hover:bg-indigo-500 text-white"
                    >
                      {candidateMutation.isPending ? <Spinner size="sm" /> : 'Synthesize'}
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {candidateMutation.isPending && (
            <div className="p-12 text-center">
              <Spinner size="lg" className="mx-auto mb-4 text-indigo-400" />
              <p className="text-slate-300 font-medium">Analyzing multi-round feedback and rubric scores...</p>
            </div>
          )}

          {candidateMutation.data && (
            <div className="space-y-6">
              {/* Header Card */}
              <Card className="bg-surface-card border-surface-border">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="text-lg">{candidateMutation.data.candidate_name}</CardTitle>
                      <CardDescription>
                        Evaluations: {candidateMutation.data.evaluations_count} • Status: {candidateMutation.data.pipeline_status}
                      </CardDescription>
                    </div>
                    {candidateMutation.data.average_score !== undefined && (
                      <div className="text-right">
                        <span className="text-xs text-slate-400 block">Average Score</span>
                        <span className="text-2xl font-bold text-indigo-400">
                          {candidateMutation.data.average_score} <span className="text-xs text-slate-500">/ 10</span>
                        </span>
                      </div>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="p-4 bg-slate-900/60 rounded-xl border border-surface-border">
                    <span className="text-xs font-semibold text-slate-400 block mb-1">Readiness Assessment:</span>
                    <p className="text-sm text-slate-200">{candidateMutation.data.progression_readiness}</p>
                  </div>

                  <p className="text-sm text-slate-300 leading-relaxed">
                    {candidateMutation.data.recommendation_synthesis}
                  </p>
                  <p className="text-xs text-slate-400">{candidateMutation.data.disclaimer}</p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-4 bg-emerald-950/20 border border-emerald-800/30 rounded-xl">
                      <span className="text-xs font-semibold text-emerald-400 block mb-2">Synthesized Strengths:</span>
                      <ul className="list-disc list-inside text-xs text-slate-300 space-y-1">
                        {candidateMutation.data.recurring_strengths.map((s, i) => (
                          <li key={i}>{s}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="p-4 bg-amber-950/20 border border-amber-800/30 rounded-xl">
                      <span className="text-xs font-semibold text-amber-400 block mb-2">Areas for Evaluation / Growth:</span>
                      <ul className="list-disc list-inside text-xs text-slate-300 space-y-1">
                        {candidateMutation.data.recurring_weaknesses.map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: Ask Copilot (Q&A) */}
      {activeTab === 'ask' && (
        <div className="space-y-6">
          <Card className="bg-surface-card border-surface-border">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-indigo-400" />
                Ask Recruitment Data Assistant
              </CardTitle>
              <CardDescription>
                Ask natural-language queries about candidate pipelines, interviewer workloads, and pending evaluations.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Sample Query Chips */}
              <div className="flex flex-wrap gap-2">
                {[
                  'Which interviewers have the highest workload?',
                  'Which candidates are awaiting evaluation?',
                  'What is the scheduling status of our drives?',
                  'Show candidates with active interviews scheduled',
                ].map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => setAskQuery(q)}
                    className="text-xs py-1 px-2.5 rounded-full bg-slate-900 border border-surface-border text-slate-300 hover:border-indigo-500/50 hover:text-indigo-300 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>

              <div className="flex gap-2">
                <Input
                  value={askQuery}
                  onChange={(e) => setAskQuery(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && askQuery.trim()) {
                      askMutation.mutate();
                    }
                  }}
                  placeholder="e.g. Which interviewers have the highest workload?"
                  className="flex-1"
                />
                <Button
                  onClick={() => askMutation.mutate()}
                  disabled={askMutation.isPending || !askQuery.trim()}
                  className="bg-indigo-600 hover:bg-indigo-500 text-white flex items-center gap-2"
                >
                  {askMutation.isPending ? <Spinner size="sm" /> : <Send className="w-4 h-4" />}
                  Ask
                </Button>
              </div>
            </CardContent>
          </Card>

          {askMutation.isPending && (
            <Card className="bg-surface-card border-surface-border p-8 text-center">
              <Spinner size="md" className="mx-auto mb-3 text-indigo-400" />
              <p className="text-sm text-slate-300">Querying recruitment database and compiling response...</p>
            </Card>
          )}

          {askMutation.data && (
            <Card className="bg-surface-card border-surface-border">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base text-slate-200">"{askMutation.data.question}"</CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-xs bg-indigo-500/10 text-indigo-300 border-indigo-500/30">
                      {askMutation.data.data_points_analyzed} evidence items
                    </Badge>
                    <Badge variant="outline" className="text-xs">
                      {askMutation.data.is_ai_generated
                        ? `AI · ${askMutation.data.provider_used}`
                        : 'Rule-based'}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="p-4 bg-slate-900/80 rounded-xl border border-surface-border">
                  <p className="text-sm text-slate-100 whitespace-pre-line leading-relaxed">
                    {askMutation.data.answer}
                  </p>
                </div>

                {askMutation.data.suggested_followups.length > 0 && (
                  <div>
                    <span className="text-xs font-semibold text-slate-400 block mb-2">Suggested Follow-ups:</span>
                    <div className="flex flex-wrap gap-2">
                      {askMutation.data.suggested_followups.map((f, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => {
                            setAskQuery(f);
                            askMutation.mutate();
                          }}
                          className="text-xs py-1 px-3 rounded-lg bg-surface-card border border-surface-border text-indigo-300 hover:bg-indigo-950/30 transition-colors flex items-center gap-1.5"
                        >
                          {f}
                          <ArrowRight className="w-3 h-3" />
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
};
