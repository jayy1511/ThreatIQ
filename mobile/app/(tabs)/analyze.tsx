// Analyze Screen - Matches Web UI with cold-start handling
import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { ScreenContainer, Card, Button, Input, Tag } from '../../src/components';
import { useAuth } from '../../src/lib/auth';
import {
    analyze,
    analyzePublic,
    checkServiceHealth,
    AnalysisResponse,
    ApiError,
    ServiceHealthStatus
} from '../../src/lib/api';
import { colors, spacing, fontSize, borderRadius } from '../../src/theme/colors';

export default function AnalyzeScreen() {
    const { user } = useAuth();
    const [message, setMessage] = useState('');
    const [userGuess, setUserGuess] = useState<'phishing' | 'safe' | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<AnalysisResponse | null>(null);
    const [serviceStatus, setServiceStatus] = useState<ServiceHealthStatus | null>(null);
    const [checkingHealth, setCheckingHealth] = useState(false);

    // Check service health on mount
    useEffect(() => {
        checkHealth();
    }, []);

    const checkHealth = async () => {
        setCheckingHealth(true);
        const status = await checkServiceHealth();
        setServiceStatus(status);
        setCheckingHealth(false);
    };

    const handleAnalyze = async () => {
        if (!message.trim()) return;

        setLoading(true);
        setError(null);
        setResult(null);

        try {
            let response: AnalysisResponse;

            if (user) {
                response = await analyze(message, user.uid, userGuess || undefined);
            } else {
                response = await analyzePublic(message, userGuess || undefined);
            }

            setResult(response);
            setServiceStatus({ status: 'ready' }); // Service is now warm
        } catch (err) {
            if (err instanceof ApiError) {
                if (err.isWarmingUp) {
                    setError('🔄 Service is warming up. Please wait 30 seconds and try again.');
                    setServiceStatus({ status: 'warming_up', retry_after_seconds: 30 });
                } else {
                    setError(err.message);
                }
            } else {
                setError('Failed to analyze message. Please try again.');
            }
        } finally {
            setLoading(false);
        }
    };

    const clearResult = () => {
        setResult(null);
        setMessage('');
        setUserGuess(null);
        setError(null);
    };

    const getLabelVariant = (label: string): 'success' | 'warning' | 'error' => {
        switch (label.toLowerCase()) {
            case 'safe': return 'success';
            case 'suspicious': return 'warning';
            case 'phishing': return 'error';
            default: return 'warning';
        }
    };

    const getLabelEmoji = (label: string) => {
        switch (label.toLowerCase()) {
            case 'safe': return '✅';
            case 'suspicious': return '⚠️';
            case 'phishing': return '🎣';
            default: return '❓';
        }
    };

    return (
        <ScreenContainer keyboard>
            <Text style={styles.title}>Analyze Message</Text>
            <Text style={styles.subtitle}>
                Paste a suspicious email or SMS to check for phishing
            </Text>

            {/* Service Status Banner */}
            {serviceStatus?.status === 'warming_up' && (
                <View style={styles.warmupBanner}>
                    <Text style={styles.warmupText}>
                        ⏳ Server is waking up... this may take 20-30 seconds
                    </Text>
                    <Button
                        title="Check Again"
                        onPress={checkHealth}
                        loading={checkingHealth}
                        variant="outline"
                        size="sm"
                    />
                </View>
            )}

            {!result ? (
                <>
                    {/* Message Input */}
                    <View style={styles.inputContainer}>
                        <Input
                            label="Message Content"
                            placeholder="Paste the suspicious message here..."
                            value={message}
                            onChangeText={setMessage}
                            multiline
                            numberOfLines={6}
                            containerStyle={styles.messageInput}
                        />
                    </View>

                    {/* Prediction Toggle (matches web) */}
                    <Text style={styles.guessLabel}>
                        What do you think? (optional - helps you learn!)
                    </Text>
                    <View style={styles.predictionToggle}>
                        <TouchableOpacity
                            style={[
                                styles.predictionButton,
                                userGuess === 'phishing' && styles.predictionButtonActive,
                                userGuess === 'phishing' && styles.predictionPhishing,
                            ]}
                            onPress={() => setUserGuess(userGuess === 'phishing' ? null : 'phishing')}
                        >
                            <Text style={styles.predictionEmoji}>🎣</Text>
                            <Text style={[
                                styles.predictionText,
                                userGuess === 'phishing' && styles.predictionTextActive
                            ]}>Phishing</Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                            style={[
                                styles.predictionButton,
                                userGuess === 'safe' && styles.predictionButtonActive,
                                userGuess === 'safe' && styles.predictionSafe,
                            ]}
                            onPress={() => setUserGuess(userGuess === 'safe' ? null : 'safe')}
                        >
                            <Text style={styles.predictionEmoji}>✅</Text>
                            <Text style={[
                                styles.predictionText,
                                userGuess === 'safe' && styles.predictionTextActive
                            ]}>Safe</Text>
                        </TouchableOpacity>
                    </View>

                    {/* Error Message */}
                    {error && (
                        <View style={styles.errorContainer}>
                            <Text style={styles.errorText}>{error}</Text>
                        </View>
                    )}

                    {/* Analyze Button (matches web purple) */}
                    <Button
                        title={loading ? "Analyzing..." : "🔍 Analyze Message"}
                        onPress={handleAnalyze}
                        fullWidth
                        loading={loading}
                        disabled={!message.trim()}
                        style={styles.analyzeButton}
                    />
                </>
            ) : (
                <ScrollView showsVerticalScrollIndicator={false}>
                    {/* Main Result Card */}
                    <Card style={styles.resultCard}>
                        <View style={styles.resultHeader}>
                            <Text style={styles.resultEmoji}>
                                {getLabelEmoji(result.classification.label)}
                            </Text>
                            <View style={styles.resultInfo}>
                                <Text style={styles.resultLabel}>
                                    {result.classification.label.toUpperCase()}
                                </Text>
                                <Text style={styles.confidenceText}>
                                    {Math.round(result.classification.confidence * 100)}% confidence
                                </Text>
                            </View>
                        </View>

                        {/* Confidence Bar */}
                        <View style={styles.progressBar}>
                            <View
                                style={[
                                    styles.progressFill,
                                    {
                                        width: `${result.classification.confidence * 100}%`,
                                        backgroundColor: result.classification.label === 'safe'
                                            ? colors.success
                                            : result.classification.label === 'suspicious'
                                                ? colors.warning
                                                : colors.error
                                    }
                                ]}
                            />
                        </View>

                        {/* User Prediction Feedback */}
                        {result.was_correct !== null && result.was_correct !== undefined && (
                            <View style={[
                                styles.feedbackBanner,
                                result.was_correct ? styles.feedbackCorrect : styles.feedbackIncorrect
                            ]}>
                                <Text style={styles.feedbackText}>
                                    {result.was_correct
                                        ? '🎉 Great job! Your prediction was correct!'
                                        : '📚 Keep learning! Your prediction was incorrect.'}
                                </Text>
                            </View>
                        )}
                    </Card>

                    {/* Reason Tags */}
                    {result.classification.reason_tags?.length > 0 && (
                        <Card>
                            <Text style={styles.sectionTitle}>🏷️ Detected Indicators</Text>
                            <View style={styles.tagsContainer}>
                                {result.classification.reason_tags.map((tag, i) => (
                                    <Tag key={i} label={tag} variant="accent" size="sm" style={styles.tag} />
                                ))}
                            </View>
                        </Card>
                    )}

                    {/* Explanation */}
                    <Card>
                        <Text style={styles.sectionTitle}>📋 Analysis Details</Text>
                        <Text style={styles.explanationText}>{result.classification.explanation}</Text>
                    </Card>

                    {/* AI Coach Response */}
                    {result.coach_response && (
                        <Card variant="accent">
                            <Text style={styles.sectionTitle}>🎓 AI Coach Says</Text>
                            <Text style={styles.coachText}>
                                {result.coach_response.verdict}{'\n\n'}
                                {result.coach_response.explanation}
                            </Text>
                        </Card>
                    )}

                    {/* Similar Examples */}
                    {result.coach_response?.similar_examples?.length > 0 && (
                        <Card>
                            <Text style={styles.sectionTitle}>📚 Similar Examples</Text>
                            {result.coach_response.similar_examples.slice(0, 3).map((example, i) => (
                                <View key={i} style={styles.exampleItem}>
                                    <View style={styles.exampleHeader}>
                                        <Tag
                                            label={example.category}
                                            variant={getLabelVariant(example.category)}
                                            size="sm"
                                        />
                                        <Text style={styles.similarityText}>
                                            {Math.round((example.similarity || 0) * 100)}% match
                                        </Text>
                                    </View>
                                    <Text style={styles.exampleText} numberOfLines={2}>
                                        {example.message}
                                    </Text>
                                </View>
                            ))}
                        </Card>
                    )}

                    {/* New Analysis Button */}
                    <Button
                        title="📝 Analyze Another Message"
                        onPress={clearResult}
                        variant="primary"
                        fullWidth
                        style={styles.newAnalysisButton}
                    />
                </ScrollView>
            )}
        </ScreenContainer>
    );
}

const styles = StyleSheet.create({
    title: {
        fontSize: fontSize.xxxl,
        fontWeight: 'bold',
        color: colors.text,
        marginBottom: spacing.xs,
    },
    subtitle: {
        fontSize: fontSize.md,
        color: colors.textMuted,
        marginBottom: spacing.md,
    },
    warmupBanner: {
        backgroundColor: colors.warningBg,
        padding: spacing.md,
        borderRadius: borderRadius.md,
        marginBottom: spacing.md,
        alignItems: 'center',
        gap: spacing.sm,
    },
    warmupText: {
        color: colors.warning,
        fontSize: fontSize.sm,
        textAlign: 'center',
    },
    inputContainer: {
        marginBottom: spacing.md,
    },
    messageInput: {
        minHeight: 150,
    },
    guessLabel: {
        fontSize: fontSize.sm,
        color: colors.textMuted,
        marginBottom: spacing.sm,
    },
    predictionToggle: {
        flexDirection: 'row',
        gap: spacing.sm,
        marginBottom: spacing.lg,
    },
    predictionButton: {
        flex: 1,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: spacing.sm,
        paddingVertical: spacing.md,
        borderRadius: borderRadius.md,
        backgroundColor: colors.card,
        borderWidth: 2,
        borderColor: colors.cardBorder,
    },
    predictionButtonActive: {
        borderColor: colors.primary,
    },
    predictionPhishing: {
        backgroundColor: colors.errorBg,
        borderColor: colors.error,
    },
    predictionSafe: {
        backgroundColor: colors.successBg,
        borderColor: colors.success,
    },
    predictionEmoji: {
        fontSize: 20,
    },
    predictionText: {
        fontSize: fontSize.md,
        fontWeight: '600',
        color: colors.textMuted,
    },
    predictionTextActive: {
        color: colors.text,
    },
    errorContainer: {
        backgroundColor: colors.errorBg,
        borderRadius: borderRadius.md,
        padding: spacing.md,
        marginBottom: spacing.md,
    },
    errorText: {
        color: colors.error,
        fontSize: fontSize.sm,
        textAlign: 'center',
    },
    analyzeButton: {
        marginBottom: spacing.lg,
    },
    resultCard: {
        marginBottom: spacing.md,
    },
    resultHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: spacing.md,
        marginBottom: spacing.md,
    },
    resultEmoji: {
        fontSize: 48,
    },
    resultInfo: {
        flex: 1,
    },
    resultLabel: {
        fontSize: fontSize.xxl,
        fontWeight: 'bold',
        color: colors.text,
    },
    confidenceText: {
        fontSize: fontSize.md,
        color: colors.textMuted,
        marginTop: 2,
    },
    progressBar: {
        height: 8,
        backgroundColor: colors.inputBackground,
        borderRadius: 4,
        overflow: 'hidden',
        marginBottom: spacing.md,
    },
    progressFill: {
        height: '100%',
        borderRadius: 4,
    },
    feedbackBanner: {
        padding: spacing.md,
        borderRadius: borderRadius.md,
        alignItems: 'center',
    },
    feedbackCorrect: {
        backgroundColor: colors.successBg,
    },
    feedbackIncorrect: {
        backgroundColor: colors.warningBg,
    },
    feedbackText: {
        fontSize: fontSize.sm,
        fontWeight: '500',
        color: colors.text,
        textAlign: 'center',
    },
    sectionTitle: {
        fontSize: fontSize.lg,
        fontWeight: '600',
        color: colors.text,
        marginBottom: spacing.sm,
    },
    tagsContainer: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: spacing.xs,
    },
    tag: {
        marginBottom: spacing.xs,
    },
    explanationText: {
        fontSize: fontSize.md,
        color: colors.textSecondary,
        lineHeight: 24,
    },
    coachText: {
        fontSize: fontSize.md,
        color: colors.textSecondary,
        lineHeight: 24,
        fontStyle: 'italic',
    },
    exampleItem: {
        paddingVertical: spacing.sm,
        borderBottomWidth: 1,
        borderBottomColor: colors.cardBorder,
    },
    exampleHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: spacing.xs,
    },
    similarityText: {
        fontSize: fontSize.sm,
        color: colors.textMuted,
    },
    exampleText: {
        fontSize: fontSize.sm,
        color: colors.textMuted,
    },
    newAnalysisButton: {
        marginTop: spacing.md,
        marginBottom: spacing.xxl,
    },
});
