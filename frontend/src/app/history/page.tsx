'use client';

import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/context/AuthContext';
import ProtectedRoute from '@/components/ProtectedRoute';
import {
  getUserHistory,
  deleteHistoryItem,
  clearHistory,
  updatePrivacySettings,
} from '@/lib/api';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Shield,
  Clock,
  AlertTriangle,
  CheckCircle,
  Trash2,
  EyeOff,
  Eye,
  RefreshCw,
} from 'lucide-react';

type HistoryItem = {
  id?: string;
  message: string | null;
  classification?: {
    label?: string;
    confidence?: number;
  };
  was_correct?: boolean | null;
  session_id?: string;
  timestamp?: string | null;
};

export default function HistoryPage() {
  const { user, loading: authLoading } = useAuth();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [saveText, setSaveText] = useState(true);
  const [updatingPrivacy, setUpdatingPrivacy] = useState(false);

  const fetchHistory = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getUserHistory(user.uid);
      setHistory(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Error loading history:', err);
      setError('Failed to load history.');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const handleDelete = async (itemId: string) => {
    if (!user || !itemId) return;
    setDeletingId(itemId);
    try {
      await deleteHistoryItem(user.uid, itemId);
      setHistory((prev) => prev.filter((h) => h.id !== itemId));
    } catch {
      setError('Failed to delete item.');
    } finally {
      setDeletingId(null);
    }
  };

  const handleClearAll = async () => {
    if (!user) return;
    if (!window.confirm('Delete all your history? This cannot be undone.')) return;
    setClearing(true);
    try {
      await clearHistory(user.uid);
      setHistory([]);
    } catch {
      setError('Failed to clear history.');
    } finally {
      setClearing(false);
    }
  };

  const handlePrivacyToggle = async () => {
    if (!user) return;
    const newValue = !saveText;
    setUpdatingPrivacy(true);
    try {
      await updatePrivacySettings(user.uid, newValue);
      setSaveText(newValue);
    } catch {
      setError('Failed to update privacy setting.');
    } finally {
      setUpdatingPrivacy(false);
    }
  };

  if (loading || authLoading) {
    return (
      <ProtectedRoute>
        <div className="flex items-center justify-center min-h-screen">
          Loading history...
        </div>
      </ProtectedRoute>
    );
  }

  const sorted = [...history].sort((a, b) => {
    const ta = a.timestamp ? new Date(a.timestamp).getTime() : 0;
    const tb = b.timestamp ? new Date(b.timestamp).getTime() : 0;
    return tb - ta;
  });

  return (
    <ProtectedRoute>
      <div className="container mx-auto py-10 px-4 max-w-5xl">
        {/* Header row */}
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">History</h1>
            <p className="text-muted-foreground mt-2">
              Review your past analyses and see how your detection skills evolve over time.
            </p>
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap items-center gap-2 flex-shrink-0">
            {/* Privacy toggle */}
            <Button
              id="privacy-toggle-btn"
              variant="outline"
              size="sm"
              onClick={handlePrivacyToggle}
              disabled={updatingPrivacy}
              title={
                saveText
                  ? 'Message text is currently saved. Click to stop saving.'
                  : 'Message text is NOT saved. Click to enable saving.'
              }
              className="flex items-center gap-2"
            >
              {saveText ? (
                <>
                  <Eye className="h-4 w-4" />
                  <span>Text saved</span>
                </>
              ) : (
                <>
                  <EyeOff className="h-4 w-4 text-muted-foreground" />
                  <span className="text-muted-foreground">Text hidden</span>
                </>
              )}
            </Button>

            {/* Refresh */}
            <Button
              id="refresh-history-btn"
              variant="ghost"
              size="sm"
              onClick={fetchHistory}
              title="Refresh history"
            >
              <RefreshCw className="h-4 w-4" />
            </Button>

            {/* Clear all */}
            {sorted.length > 0 && (
              <Button
                id="clear-all-history-btn"
                variant="destructive"
                size="sm"
                onClick={handleClearAll}
                disabled={clearing}
                className="flex items-center gap-2"
              >
                <Trash2 className="h-4 w-4" />
                {clearing ? 'Clearing…' : 'Clear All'}
              </Button>
            )}
          </div>
        </div>

        {/* Privacy notice */}
        {!saveText && (
          <Card className="mb-6 border-amber-400/60 bg-amber-50/50 dark:bg-amber-950/20">
            <CardContent className="flex items-start gap-3 pt-4 pb-4">
              <EyeOff className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-amber-700 dark:text-amber-400">
                <strong>Text storage is disabled.</strong> New analyses will only store metadata
                (verdict, confidence, timestamp) — not the message text itself.
                Previously saved message text is unaffected.
              </p>
            </CardContent>
          </Card>
        )}

        {error && (
          <Card className="mb-6 border-red-500/60">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-red-600">
                <AlertTriangle className="h-5 w-5" />
                Error
              </CardTitle>
              <CardDescription>{error}</CardDescription>
            </CardHeader>
          </Card>
        )}

        {sorted.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="flex flex-col items-center justify-center py-10 text-center">
              <Shield className="h-10 w-10 text-muted-foreground mb-3" />
              <p className="text-muted-foreground">
                No history available yet. Analyze a few messages to see them listed here.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {sorted.map((item) => {
              const label = item.classification?.label ?? 'unknown';
              const confidence =
                item.classification?.confidence != null
                  ? Math.round(item.classification.confidence * 100)
                  : null;

              const isPhishing = label === 'phishing';
              const isSafe = label === 'safe';

              const ts = item.timestamp ? new Date(item.timestamp) : null;
              const timeLabel = ts ? ts.toLocaleString() : 'Unknown time';
              const itemId = item.id ?? '';

              const messageText = item.message;
              const isRedacted = messageText === null || messageText === undefined;

              return (
                <Card key={itemId || timeLabel}>
                  <CardHeader className="flex flex-row items-start justify-between gap-4">
                    <div className="space-y-1 min-w-0 flex-1">
                      <CardTitle className="text-sm font-semibold break-words">
                        {isRedacted ? (
                          <span className="italic text-muted-foreground flex items-center gap-1.5">
                            <EyeOff className="h-3.5 w-3.5 flex-shrink-0" />
                            Message text not saved
                          </span>
                        ) : (
                          <>
                            {messageText!.slice(0, 80)}
                            {messageText!.length > 80 && '…'}
                          </>
                        )}
                      </CardTitle>
                      <CardDescription className="flex items-center gap-2 text-xs">
                        <Clock className="h-3 w-3 flex-shrink-0" />
                        <span>{timeLabel}</span>
                      </CardDescription>
                    </div>

                    <div className="flex flex-col items-end gap-1 flex-shrink-0">
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={
                            isPhishing ? 'destructive' : isSafe ? 'outline' : 'secondary'
                          }
                          className="uppercase"
                        >
                          {label}
                        </Badge>

                        {/* Delete button */}
                        {itemId && (
                          <Button
                            id={`delete-item-${itemId}`}
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0 text-muted-foreground hover:text-red-500"
                            onClick={() => handleDelete(itemId)}
                            disabled={deletingId === itemId}
                            title="Delete this entry"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>

                      {confidence !== null && (
                        <span className="text-xs text-muted-foreground whitespace-nowrap">
                          Confidence: {confidence}%
                        </span>
                      )}
                      {item.was_correct != null && (
                        <span className="flex items-center gap-1 text-xs whitespace-nowrap">
                          {item.was_correct ? (
                            <>
                              <CheckCircle className="h-3 w-3 text-green-500 flex-shrink-0" />
                              <span className="text-green-500">You were right</span>
                            </>
                          ) : (
                            <>
                              <AlertTriangle className="h-3 w-3 text-red-500 flex-shrink-0" />
                              <span className="text-red-500">Your guess was incorrect</span>
                            </>
                          )}
                        </span>
                      )}
                    </div>
                  </CardHeader>

                  {/* Full message text body — only shown if not redacted */}
                  {!isRedacted && messageText && (
                    <CardContent>
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap break-words">
                        {messageText}
                      </p>
                    </CardContent>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </ProtectedRoute>
  );
}
