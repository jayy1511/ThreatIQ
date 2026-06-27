'use client';

import { useState } from 'react';
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
} from 'lucide-react';
import { analyzeMessage, analyzePublicMessage } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import ProtectedRoute from '@/components/ProtectedRoute';

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
}

export default function AnalyzePage() {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [userGuess, setUserGuess] = useState<'phishing' | 'safe' | null>(null);
  const [quizAnswer, setQuizAnswer] = useState<{ selected: string | null, isCorrect: boolean | null }>({ selected: null, isCorrect: null });
  const { user } = useAuth();

  const handleAnalyze = async (skipGuess: boolean = false) => {
    if (!message.trim()) return;

    if (!user) {
      alert('Please sign in to use the full analysis tool.');
      return;
    }

    // Prevent double submission
    if (loading) {
      return;
    }

    setError(null);
    setLoading(true);

    // Use the user's guess, or 'unclear' if they skipped
    const guessToSend = skipGuess ? 'unclear' : (userGuess || 'unclear');

    try {
      let data;

      try {
        data = await analyzeMessage(message, guessToSend, user.uid);
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } }).response?.status;

        // Only fall back to public endpoint for auth errors (401/403)
        // Do NOT fallback for 500 errors - those indicate real problems
        if (status === 401 || status === 403) {
          console.warn('Auth error, falling back to public endpoint:', err);
          data = await analyzePublicMessage(message, guessToSend);
        } else if (status === 429) {
          setError('Quota gratuite atteinte. Réessaie plus tard ou utilise une autre clé API.');
          return;
        } else {
          // For all other errors (including 500), don't fallback
          throw err;
        }
      }

      setResult(data);
      setQuizAnswer({ selected: null, isCorrect: null }); // Reset quiz for new analysis
    } catch (err: unknown) {
      console.error('Analysis failed:', err);
      setResult(null);

      // Handle different error types
      if ((err as { response?: { status?: number } }).response?.status === 429) {
        setError('Quota gratuite atteinte. Réessaie plus tard.');
      } else {
        setError('Analysis failed. Please try again in a moment.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
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

          {/* 2-column layout so the input box is wider */}
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
                      {loading ? 'Analyzing...' : 'Analyze with My Prediction'}
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

              <Card>
                <CardHeader>
                  <CardTitle className="text-sm font-medium">Analysis Tips</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground space-y-2">
                  <p>Include the full message body.</p>
                  <p>Include headers if possible.</p>
                  <p>Don&apos;t click links before analyzing.</p>
                </CardContent>
              </Card>
            </div>

            {/* Results Section */}
            <div>
              {result ? (
                <div className="space-y-6">
                  {/* Verdict Card */}
                  <Card
                    className={`border-l-4 ${result.classification.label === 'phishing'
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
                        <div className={`mt-4 p-3 rounded-lg flex items-center gap-2 ${userGuess === result.classification.label
                          ? 'bg-green-500/10 border border-green-500/30'
                          : 'bg-red-500/10 border border-red-500/30'
                          }`}>
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
                                Your prediction was &quot;{userGuess}&quot; — the AI classified it as &quot;{result.classification.label}&quot;.
                              </span>
                            </>
                          )}
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  {/* Detailed Analysis Tabs */}
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
                                    const isCorrectOption = option === result.coach_response.quiz?.correct_answer;
                                    const showResult = quizAnswer.selected !== null;

                                    return (
                                      <Button
                                        key={i}
                                        variant="outline"
                                        disabled={showResult}
                                        className={`w-full justify-start h-auto py-3 px-4 whitespace-normal text-left transition-all ${showResult && isCorrectOption
                                          ? 'border-green-500 bg-green-500/10 text-green-500'
                                          : showResult && isSelected && !isCorrectOption
                                            ? 'border-red-500 bg-red-500/10 text-red-500'
                                            : ''
                                          }`}
                                        onClick={() => {
                                          const correct = option === result.coach_response.quiz?.correct_answer;
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
                                <div className={`p-3 rounded-lg flex items-center gap-2 ${quizAnswer.isCorrect
                                  ? 'bg-green-500/10 border border-green-500/30'
                                  : 'bg-red-500/10 border border-red-500/30'
                                  }`}>
                                  {quizAnswer.isCorrect ? (
                                    <>
                                      <CheckCircle className="h-5 w-5 text-green-500" />
                                      <span className="text-green-500 font-medium">Correct! Well done.</span>
                                    </>
                                  ) : (
                                    <>
                                      <AlertTriangle className="h-5 w-5 text-red-500" />
                                      <span className="text-red-500 font-medium">Not quite. The correct answer is highlighted above.</span>
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
              ) : (
                <div className="h-full flex items-center justify-center min-h-[400px] border-2 border-dashed rounded-lg text-muted-foreground">
                  <div className="text-center space-y-2">
                    <Shield className="h-12 w-12 mx-auto opacity-20" />
                    <p>Enter a message to see the analysis results here.</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </ProtectedRoute>
  );
}
