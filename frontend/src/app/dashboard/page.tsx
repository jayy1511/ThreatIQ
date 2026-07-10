'use client';

import React, { useEffect, useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/context/AuthContext';
import { getDashboard } from '@/lib/api';
import { Shield, Target, TrendingUp, AlertTriangle, CheckCircle2, XCircle, Flame, BookOpen, Mail, ArrowRight } from 'lucide-react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import ProtectedRoute from '@/components/ProtectedRoute';
import InstallPrompt from '@/components/InstallPrompt';

interface LessonProgress {
  xp_total: number;
  level: number;
  streak_current: number;
  streak_best: number;
  lessons_completed: number;
}

interface TodayLessonData {
  lesson: { lesson_id: string; title: string; topic: string };
  date: string;
  already_completed: boolean;
}

interface DashboardSummary {
  total_analyzed: number;
  accuracy: number;
  categories_seen: number;
  weak_spots: string[];
}

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [lessonProgress, setLessonProgress] = useState<LessonProgress | null>(null);
  const [todayLesson, setTodayLesson] = useState<TodayLessonData | null>(null);
  const [gmailConnected, setGmailConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [gmailToast, setGmailToast] = useState<'connected' | 'error' | null>(null);
  const searchParams = useSearchParams();

  useEffect(() => {
    const gmailParam = searchParams.get('gmail');
    if (gmailParam === 'connected') {
      setGmailToast('connected');
      setTimeout(() => setGmailToast(null), 5000);
    } else if (gmailParam === 'error') {
      setGmailToast('error');
      setTimeout(() => setGmailToast(null), 5000);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!user) return;
    const fetchData = async () => {
      try {
        // Single request replaces 4 separate API calls
        const data = await getDashboard(user.uid);
        setSummary(data.summary);
        setLessonProgress(data.lesson_progress);
        setTodayLesson(data.today_lesson);
        setGmailConnected(data.gmail?.connected ?? false);
      } catch (error) {
        console.error('Error fetching dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [user]);

  if (loading || authLoading) {
    return (
      <ProtectedRoute>
        <div className="flex items-center justify-center min-h-screen">
          Loading dashboard...
        </div>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <div className="container mx-auto py-10 px-4">
        <InstallPrompt />
        <h1 className="text-3xl font-bold tracking-tight mb-2">
          Dashboard
        </h1>
        <p className="text-muted-foreground mb-8">
          Welcome back! Here&apos;s your security training overview.
        </p>

        {gmailToast && (
          <div className="mb-6">
            {gmailToast === 'connected' ? (
              <Alert className="border-green-200 bg-green-50 dark:bg-green-950 dark:border-green-800">
                <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
                <AlertDescription className="text-green-800 dark:text-green-200">
                  Gmail connected successfully! You can now triage your inbox.
                </AlertDescription>
              </Alert>
            ) : (
              <Alert variant="destructive">
                <XCircle className="h-4 w-4" />
                <AlertDescription>
                  Failed to connect Gmail. Please try again.
                </AlertDescription>
              </Alert>
            )}
          </div>
        )}

        {/* Quick Stats */}
        <div className="grid gap-4 md:grid-cols-4 mb-8">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Analyzed</CardTitle>
              <Shield className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{summary?.total_analyzed || 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Accuracy</CardTitle>
              <Target className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{summary?.accuracy || 0}%</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Day Streak</CardTitle>
              <Flame className="h-4 w-4 text-orange-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-orange-500">{lessonProgress?.streak_current || 0}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Level</CardTitle>
              <TrendingUp className="h-4 w-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-500">Lv. {lessonProgress?.level || 1}</div>
            </CardContent>
          </Card>
        </div>

        {/* Feature Cards */}
        <div className="grid gap-6 md:grid-cols-3">
          {/* Daily Lesson Card */}
          <Card className="border-2 border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <BookOpen className="h-5 w-5 text-primary" />
                  Daily Lessons
                </CardTitle>
                {todayLesson?.already_completed && (
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                )}
              </div>
              <CardDescription>
                {todayLesson ? todayLesson.lesson.title : 'Complete daily micro-lessons'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-4">
                <p className="text-sm text-muted-foreground">
                  {lessonProgress?.lessons_completed || 0} lessons completed
                </p>
              </div>
              <Link href="/lessons">
                <Button className="w-full">
                  {todayLesson?.already_completed ? 'View Lessons' : 'Start Today\'s Lesson'}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </CardContent>
          </Card>

          {/* Gmail Integration Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="h-5 w-5" />
                Gmail Integration
              </CardTitle>
              <CardDescription>
                Scan your inbox for phishing threats
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-4 flex items-center gap-2">
                {gmailConnected ? (
                  <>
                    <CheckCircle2 className="h-4 w-4 text-green-500" />
                    <span className="text-sm text-green-600 dark:text-green-400">Connected</span>
                  </>
                ) : (
                  <>
                    <XCircle className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">Not connected</span>
                  </>
                )}
              </div>
              <Link href="/gmail">
                <Button variant={gmailConnected ? "outline" : "default"} className="w-full">
                  {gmailConnected ? 'Manage Gmail' : 'Connect Gmail'}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </CardContent>
          </Card>

          {/* Progress Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Flame className="h-5 w-5 text-orange-500" />
                Progress & Stats
              </CardTitle>
              <CardDescription>
                Track your learning journey
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-4 grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-muted-foreground">XP: </span>
                  <span className="font-medium">{lessonProgress?.xp_total || 0}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">Best: </span>
                  <span className="font-medium">{lessonProgress?.streak_best || 0} days</span>
                </div>
              </div>
              <Link href="/progress">
                <Button variant="outline" className="w-full">
                  View Full Stats
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>

        {/* Weak Spots Alert */}
        {summary && summary.weak_spots && summary.weak_spots.length > 0 && (
          <Card className="mt-8">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-yellow-500" />
                Areas for Improvement
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {summary.weak_spots.slice(0, 3).map((spot: string, i: number) => (
                  <span
                    key={i}
                    className="px-3 py-1 rounded-full bg-yellow-50 text-yellow-700 dark:bg-yellow-900/20 dark:text-yellow-400 text-sm capitalize"
                  >
                    {spot.replace('_', ' ')}
                  </span>
                ))}
              </div>
              <Link href="/progress" className="inline-block mt-4">
                <Button variant="link" className="p-0 h-auto">
                  View detailed analytics →
                </Button>
              </Link>
            </CardContent>
          </Card>
        )}
      </div>
    </ProtectedRoute>
  );
}
