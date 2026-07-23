'use client';

import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter,
} from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import {
  Shield,
  AlertTriangle,
  CheckCircle,
  Brain,
  BookOpen,
  History,
  Loader2,
  FileDown,
} from 'lucide-react';
import { analyzePublicMessage, streamAnalyzeMessage } from '@/lib/api';
import type { StreamEvent, StreamStage, SenderVerification } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import ProtectedRoute from '@/components/ProtectedRoute';
import { AnalysisReport } from '@/components/AnalysisReport';
import { SenderVerificationCard } from '@/components/SenderVerificationCard';

// ─── Types ────────────────────────────────────────────────────────────────────

interface SimilarExample {
  category: string;
  similarity: number;
  message: string;
}

interface QuizData {
  question: string;
  options: string[];
  correct_answer: string;
}

interface CoachResponse {
  explanation: string;
  tips: string[];
  similar_examples: SimilarExample[];
  quiz: QuizData | null;
}

interface Classification {
  label: string;
  confidence: number;
  explanation: string;
  reason_tags: string[];
}

interface AnalysisResult {
  classification: Classification;
  coach_response: CoachResponse;
  // C5: optional sender verification result
  sender_verification?: SenderVerification | null;
}

// ─── Stage progress config ────────────────────────────────────────────────────

/** Labels shown in the checklist, in order. */
const STAGE_LABELS = [
  'Message received',
  'Classifying risk',
  'Gathering evidence',
  'Preparing coaching',
  'Complete',
];

/**
 * Maps SSE completion events → checklist index (0-based).
 * Intermediate *_started events are NOT in this map, so they never
 * trigger a UI update and the checklist never regresses.
 */
const COMPLETION_STAGE_IDX: Partial<Record<StreamStage, number>> = {
  started:                  0,
  classification_complete:  1,
  evidence_complete:        2,
  coach_complete:           3,
  complete:                 4,
};

// ─── Progress Card ────────────────────────────────────────────────────────────

function ProgressCard({
  completedStageIdx,
  isError,
  onRetry,
}: {
  /** Highest checklist index completed so far; -1 = nothing done yet. */
  completedStageIdx: number;
  isError: boolean;
  onRetry: () => void;
}) {
  const completedIdx = completedStageIdx;

  return (
    <Card className="border-l-4 border-l-primary">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          {isError ? (
            <AlertTriangle className="h-5 w-5 text-red-500" />
          ) : (
            <Brain className="h-5 w-5 text-primary animate-pulse" />
          )}
          {isError ? 'Analysis failed' : 'Analyzing…'}
        </CardTitle>
        <CardDescription>
          {isError
            ? 'Something went wrong. Please try again.'
            : 'AI agents are working through each step.'}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="space-y-3">
          {STAGE_LABELS.map((label, i) => {
            const done = completedIdx >= i;
            const active = !isError && !done && completedIdx === i - 1;
            return (
              <li key={label} className="flex items-center gap-3">
                {done ? (
                  <CheckCircle className="h-5 w-5 text-green-500 shrink-0" />
                ) : active ? (
                  <Loader2 className="h-5 w-5 text-primary shrink-0 animate-spin" />
                ) : (
                  <div className="h-5 w-5 rounded-full border-2 border-muted shrink-0" />
                )}
                <span
                  className={
                    done
                      ? 'text-green-500 font-medium'
                      : active
                      ? 'text-primary font-medium'
                      : 'text-muted-foreground'
                  }
                >
                  {label}
                </span>
              </li>
            );
          })}
        </ul>
      </CardContent>
      {isError && (
        <CardFooter>
          <Button onClick={onRetry} variant="outline" size="sm">
            Retry
          </Button>
        </CardFooter>
      )}
    </Card>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AnalyzePage() {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [userGuess, setUserGuess] = useState<'phishing' | 'safe' | null>(null);
  const [quizAnswer, setQuizAnswer] = useState<{ selected: string | null; isCorrect: boolean | null }>({
    selected: null,
    isCorrect: null,
  });

  // Streaming state
  // completedStageIdx: highest checklist index reached (-1 = not started)
  // This ONLY increases — never goes backwards, even when *_started events arrive.
  const [completedStageIdx, setCompletedStageIdx] = useState(-1);
  const [streamError, setStreamError] = useState(false);
  const streamRef = useRef<{ abort: () => void } | null>(null);

  // C5: optional email header text for sender verification
  const [headerText, setHeaderText] = useState('');
  const [showHeaderInput, setShowHeaderInput] = useState(false);

  // Export state: when the last analysis was run (for the PDF report)
  const [analysedAt, setAnalysedAt] = useState<Date | null>(null);

  // createPortal requires the component to be mounted on the client
  const [isMounted, setIsMounted] = useState(false);
  useEffect(() => { setIsMounted(true); }, []);

  const { user } = useAuth();

  // Clean up on unmount
  useEffect(() => {
    return () => { streamRef.current?.abort(); };
  }, []);

  const handleAnalyze = async (skipGuess: boolean = false) => {
    if (!message.trim() || loading) return;

    if (!user) {
      alert('Please sign in to use the full analysis tool.');
      return;
    }

    // Reset state
    setError(null);
    setResult(null);
    setCompletedStageIdx(-1);
    setStreamError(false);
    setAnalysedAt(null);
    setLoading(true);

    const guessToSend = skipGuess ? 'unclear' : (userGuess || 'unclear');

    // ── Try streaming endpoint first ───────────────────────────────────────
    let streamSucceeded = false;

    await new Promise<void>((resolve) => {
      streamRef.current?.abort();

      const handle = streamAnalyzeMessage(
        message,
        guessToSend,
        user.uid,
        (event: StreamEvent) => {
          // Only advance the checklist on completion events — never on *_started events.
          // This prevents the UI from going backwards when an intermediate event arrives.
          const idx = COMPLETION_STAGE_IDX[event.stage];
          if (idx !== undefined) {
            setCompletedStageIdx((prev) => Math.max(prev, idx));
          }

          if (event.stage === 'complete') {
            streamSucceeded = true;
            setResult(event.result as AnalysisResult);
            setAnalysedAt(new Date());
            setLoading(false);
            resolve();
          } else if (event.stage === 'error') {
            // Will fall back to regular endpoint below
            setStreamError(true);
            resolve();
          }
        },
        // C5: pass headerText when provided
        headerText || undefined,
      );

      streamRef.current = handle;

      // Safety timeout: if stream hangs for 130 s, fall back
      const timeout = setTimeout(() => {
        handle.abort();
        setStreamError(true);
        resolve();
      }, 130_000);

      // Clear timeout when promise resolves normally
      const origResolve = resolve;
      (resolve as unknown as { _timeout: ReturnType<typeof setTimeout> })._timeout = timeout;
      void origResolve;
      // We rely on the event handlers above to call resolve()
      // The timeout is a safety net; clear it in the complete/error branches above.
      // (The timeout will fire and resolve() is idempotent.)
      return () => clearTimeout(timeout);
    });

    if (streamSucceeded) return;

    // ── Fallback: regular non-streaming endpoint ───────────────────────────
    try {
      const { analyzeMessage } = await import('@/lib/api');
      let data;
      try {
        data = await analyzeMessage(message, guessToSend, user.uid);
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } }).response?.status;
        if (status === 401 || status === 403) {
          data = await analyzePublicMessage(message, guessToSend);
        } else if (status === 429) {
          setError('Rate limit reached. Please try again later.');
          return;
        } else {
          throw err;
        }
      }
      setResult(data);
      setQuizAnswer({ selected: null, isCorrect: null });
    } catch (err: unknown) {
      console.error('Analysis failed:', err);
      setResult(null);
      if ((err as { response?: { status?: number } }).response?.status === 429) {
        setError('Rate limit reached. Please try again later.');
      } else {
        setError('Analysis failed. Please try again in a moment.');
      }
    } finally {
      setLoading(false);
      setCompletedStageIdx(-1);
      setStreamError(false);
    }
  };

  return (
    <>
    <ProtectedRoute>
      <div className="container mx-auto py-10 px-4 max-w-7xl">
        <div className="flex flex-col gap-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Threat Analysis</h1>
            <p className="text-muted-foreground mt-2">
              Analyze suspicious messages with our multi-agent AI system.
            </p>
            {error && (
              <Alert variant="destructive" className="mt-4">
                <AlertTitle>Analysis failed</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </div>

          {/* 2-column layout */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Input Section */}
            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Message Input</CardTitle>
                  <CardDescription>Paste the content you want to analyze.</CardDescription>
                </CardHeader>
                <CardContent>
                  <Textarea
                    placeholder="Paste email body, SMS, or social media message..."
                    className="min-h-[300px] resize-none font-mono text-sm"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    disabled={loading}
                  />
                </CardContent>
                <CardFooter className="flex flex-col gap-4">
                  <div className="w-full space-y-2">
                    <p className="text-sm font-medium text-center">What do you think this message is?</p>
                    <div className="flex gap-2">
                      <Button
                        variant={userGuess === 'phishing' ? 'default' : 'outline'}
                        className={`flex-1 ${userGuess === 'phishing' ? 'bg-red-600 hover:bg-red-700' : ''}`}
                        onClick={() => setUserGuess('phishing')}
                        disabled={loading}
                      >
                        <AlertTriangle className="h-4 w-4 mr-2" />
                        Phishing
                      </Button>
                      <Button
                        variant={userGuess === 'safe' ? 'default' : 'outline'}
                        className={`flex-1 ${userGuess === 'safe' ? 'bg-green-600 hover:bg-green-700' : ''}`}
                        onClick={() => setUserGuess('safe')}
                        disabled={loading}
                      >
                        <CheckCircle className="h-4 w-4 mr-2" />
                        Safe
                      </Button>
                    </div>
                  </div>
                  <div className="w-full flex gap-2">
                    <Button
                      className="flex-1"
                      onClick={() => handleAnalyze(false)}
                      disabled={loading || !message.trim() || !userGuess}
                    >
                      {loading ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Analyzing…
                        </>
                      ) : (
                        'Analyze with My Prediction'
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      className="text-muted-foreground"
                      onClick={() => handleAnalyze(true)}
                      disabled={loading || !message.trim()}
                    >
                      Skip
                    </Button>
                  </div>
                </CardFooter>
              </Card>

              {/* C5: Optional email headers for sender verification */}
              <div className="rounded-lg border bg-card">
                <button
                  type="button"
                  className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                  onClick={() => setShowHeaderInput((v) => !v)}
                  disabled={loading}
                  aria-expanded={showHeaderInput}
                >
                  <span>Add email headers</span>
                  <span aria-hidden="true">{showHeaderInput ? '▲' : '▼'}</span>
                </button>
                {showHeaderInput && (
                  <div className="px-4 pb-4 space-y-2">
                    <p className="text-xs text-muted-foreground">
                      Optional. Paste the full email source or raw headers here to
                      improve sender verification. This is not required.
                    </p>
                    <Textarea
                      id="header-text-input"
                      placeholder="From: sender@example.com&#10;Reply-To: other@example.com&#10;Authentication-Results: mx.google.com; spf=pass; dkim=pass"
                      className="min-h-[120px] resize-none font-mono text-xs"
                      value={headerText}
                      onChange={(e) => setHeaderText(e.target.value)}
                      disabled={loading}
                      maxLength={4000}
                    />
                    {headerText.length > 0 && (
                      <p className="text-xs text-muted-foreground text-right">
                        {headerText.length}/4000 characters
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Results / Progress Section */}
            <div>
              {/* Stage progress — shown while streaming */}
              {loading && (
                <ProgressCard
                  completedStageIdx={completedStageIdx}
                  isError={streamError}
                  onRetry={() => handleAnalyze(false)}
                />
              )}

              {/* Full result — shown after streaming completes */}
              {result && !loading ? (
                <div className="space-y-6">
                  {/* ── Export button ──────────────────────────────────────── */}
                  <div className="flex items-center justify-end gap-2">
                    <Button
                      id="export-report-btn"
                      variant="outline"
                      size="sm"
                      className="flex items-center gap-2 print:hidden"
                      onClick={() => window.print()}
                    >
                      <FileDown className="h-4 w-4" />
                      Export Report
                    </Button>
                    <span className="text-xs text-muted-foreground print:hidden">
                      Choose &ldquo;Save as PDF&rdquo; in the print dialog.
                    </span>
                  </div>
                  {/* Verdict Card */}
                  <Card
                    className={`border-l-4 ${
                      result.classification.label === 'phishing'
                        ? 'border-l-red-500'
                        : result.classification.label === 'safe'
                        ? 'border-l-green-500'
                        : 'border-l-yellow-500'
                    }`}
                  >
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {result.classification.label === 'phishing' ? (
                            <Shield className="h-8 w-8 text-red-500" />
                          ) : result.classification.label === 'safe' ? (
                            <CheckCircle className="h-8 w-8 text-green-500" />
                          ) : (
                            <AlertTriangle className="h-8 w-8 text-yellow-500" />
                          )}
                          <div>
                            <CardTitle className="text-2xl capitalize">
                              {result.classification.label}
                            </CardTitle>
                            <CardDescription>
                              Confidence:{' '}
                              {Math.round(result.classification.confidence * 100)}%
                            </CardDescription>
                          </div>
                        </div>
                        <Badge
                          variant={
                            result.classification.label === 'phishing'
                              ? 'destructive'
                              : 'outline'
                          }
                        >
                          {result.classification.label.toUpperCase()}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-lg leading-relaxed">
                        {result.classification.explanation}
                      </p>

                      <div className="mt-4 flex flex-wrap gap-2">
                        {result.classification.reason_tags.map((tag: string) => (
                          <Badge key={tag} variant="secondary" className="capitalize">
                            {tag.replace(/_/g, ' ')}
                          </Badge>
                        ))}
                      </div>

                      {/* Prediction Feedback */}
                      {userGuess && (
                        <div
                          className={`mt-4 p-3 rounded-lg flex items-center gap-2 ${
                            userGuess === result.classification.label
                              ? 'bg-green-500/10 border border-green-500/30'
                              : 'bg-red-500/10 border border-red-500/30'
                          }`}
                        >
                          {userGuess === result.classification.label ? (
                            <>
                              <CheckCircle className="h-5 w-5 text-green-500" />
                              <span className="text-green-500 font-medium">
                                Nice! Your prediction was correct.
                              </span>
                            </>
                          ) : (
                            <>
                              <AlertTriangle className="h-5 w-5 text-red-500" />
                              <span className="text-red-500 font-medium">
                                Your prediction was &quot;{userGuess}&quot; — the AI classified
                                it as &quot;{result.classification.label}&quot;.
                              </span>
                            </>
                          )}
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  {/* C5: Sender Verification card — rendered only when data is present */}
                  {'sender_verification' in result && (
                    <SenderVerificationCard verification={result.sender_verification} />
                  )}

                  <Tabs defaultValue="coach" className="w-full">
                    <TabsList className="grid w-full grid-cols-3">
                      <TabsTrigger value="coach">AI Coach</TabsTrigger>
                      <TabsTrigger value="evidence">Evidence</TabsTrigger>
                      <TabsTrigger value="quiz">Quiz</TabsTrigger>
                    </TabsList>

                    <TabsContent value="coach" className="space-y-4 mt-4">
                      <Card>
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <Brain className="h-5 w-5 text-primary" />
                            Coach&apos;s Insight
                          </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                          <p>{result.coach_response.explanation}</p>

                          <div className="bg-muted p-4 rounded-lg">
                            <h4 className="font-semibold mb-2 flex items-center gap-2">
                              <BookOpen className="h-4 w-4" />
                              Safety Tips
                            </h4>
                            <ul className="space-y-2">
                              {result.coach_response.tips.map(
                                (tip: string, i: number) => (
                                  <li
                                    key={i}
                                    className="flex items-start gap-2 text-sm"
                                  >
                                    <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                                    <span>{tip}</span>
                                  </li>
                                )
                              )}
                            </ul>
                          </div>
                        </CardContent>
                      </Card>
                    </TabsContent>

                    <TabsContent value="evidence" className="mt-4">
                      <Card>
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2">
                            <History className="h-5 w-5 text-primary" />
                            Similar Examples
                          </CardTitle>
                          <CardDescription>
                            Historical examples that match this pattern.
                          </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                          {result.coach_response.similar_examples.map(
                            (ex: SimilarExample, i: number) => (
                              <div key={i} className="border p-3 rounded-md">
                                <div className="flex justify-between items-center mb-2">
                                  <Badge variant="outline">{ex.category}</Badge>
                                  <span className="text-xs text-muted-foreground">
                                    {Math.round(ex.similarity * 100)}% Match
                                  </span>
                                </div>
                                <p className="text-sm text-muted-foreground italic">
                                  &quot;{ex.message}&quot;
                                </p>
                              </div>
                            )
                          )}
                        </CardContent>
                      </Card>
                    </TabsContent>

                    <TabsContent value="quiz" className="mt-4">
                      <Card>
                        <CardHeader>
                          <CardTitle>Test Your Knowledge</CardTitle>
                        </CardHeader>
                        <CardContent>
                          {result.coach_response.quiz ? (
                            <div className="space-y-4">
                              <p className="font-medium text-lg">
                                {result.coach_response.quiz.question}
                              </p>
                              <div className="space-y-2">
                                {result.coach_response.quiz.options.map(
                                  (option: string, i: number) => {
                                    const isSelected = quizAnswer.selected === option;
                                    const isCorrectOption =
                                      option === result.coach_response.quiz?.correct_answer;
                                    const showResult = quizAnswer.selected !== null;

                                    return (
                                      <Button
                                        key={i}
                                        variant="outline"
                                        disabled={showResult}
                                        className={`w-full justify-start h-auto py-3 px-4 whitespace-normal text-left transition-all ${
                                          showResult && isCorrectOption
                                            ? 'border-green-500 bg-green-500/10 text-green-500'
                                            : showResult && isSelected && !isCorrectOption
                                            ? 'border-red-500 bg-red-500/10 text-red-500'
                                            : ''
                                        }`}
                                        onClick={() => {
                                          const correct =
                                            option === result.coach_response.quiz?.correct_answer;
                                          setQuizAnswer({ selected: option, isCorrect: correct });
                                        }}
                                      >
                                        {option}
                                        {showResult && isCorrectOption && (
                                          <CheckCircle className="ml-2 h-4 w-4 inline" />
                                        )}
                                        {showResult && isSelected && !isCorrectOption && (
                                          <AlertTriangle className="ml-2 h-4 w-4 inline" />
                                        )}
                                      </Button>
                                    );
                                  }
                                )}
                              </div>
                              {quizAnswer.selected && (
                                <div
                                  className={`p-3 rounded-lg flex items-center gap-2 ${
                                    quizAnswer.isCorrect
                                      ? 'bg-green-500/10 border border-green-500/30'
                                      : 'bg-red-500/10 border border-red-500/30'
                                  }`}
                                >
                                  {quizAnswer.isCorrect ? (
                                    <>
                                      <CheckCircle className="h-5 w-5 text-green-500" />
                                      <span className="text-green-500 font-medium">
                                        Correct! Well done.
                                      </span>
                                    </>
                                  ) : (
                                    <>
                                      <AlertTriangle className="h-5 w-5 text-red-500" />
                                      <span className="text-red-500 font-medium">
                                        Not quite. The correct answer is highlighted above.
                                      </span>
                                    </>
                                  )}
                                </div>
                              )}
                            </div>
                          ) : (
                            <p className="text-muted-foreground">
                              No quiz available for this analysis.
                            </p>
                          )}
                        </CardContent>
                      </Card>
                    </TabsContent>
                  </Tabs>
                </div>
              ) : !loading ? (
                <div className="h-full flex items-center justify-center min-h-[400px] border-2 border-dashed rounded-lg text-muted-foreground">
                  <div className="text-center space-y-2">
                    <Shield className="h-12 w-12 mx-auto opacity-20" />
                    <p>Enter a message to see the analysis results here.</p>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </ProtectedRoute>

    {/* ── Print portal ─────────────────────────────────────────────────────── */}
    {/* createPortal renders directly into document.body, bypassing all React  */}
    {/* parent wrappers. The @media print CSS hides body > * then un-hides     */}
    {/* #threat-iq-report-portal by ID (higher specificity than tag selector). */}
    {/* A stylesheet display:none (not inline) on the portal ID lets the print */}
    {/* media query override it with !important.                               */}
    {isMounted && result && !loading && createPortal(
      <div id="threat-iq-report-portal">
        <AnalysisReport
          data={{
            classification: result.classification,
            coach_response: result.coach_response,
            userGuess: userGuess,
            was_correct: userGuess
              ? userGuess === result.classification.label
              : null,
            messageText: message,
            showMessage: true,
            analysedAt: analysedAt ?? new Date(),
            category: (result as unknown as { category?: string }).category ?? null,
          }}
        />
      </div>,
      document.body
    )}
  </>
  );
}
