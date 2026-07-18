/**
 * AnalysisReport — printable PDF report component (C4).
 *
 * This component is hidden on screen (display:none) and only becomes
 * visible when the browser's @media print rules activate.  Clicking
 * "Export Report" calls window.print(), which the browser renders as
 * a PDF through the native Save-as-PDF flow.
 *
 * Privacy rules observed:
 *  - Raw message text is included only when showMessage=true (respects
 *    user's privacy preference from B7).
 *  - Long messages are truncated at 800 chars with an indicator.
 *  - No user IDs, request IDs, Firebase tokens, or debug fields.
 *  - No internal backend/session metadata.
 *
 * Styles live in globals.css under @media print so Tailwind classes
 * are NOT used here — they rely on dark-mode variants that would break
 * print readability.  Inline styles + class names matched in globals.css
 * are used instead.
 */

import React from 'react';

/* ─── Types ────────────────────────────────────────────────────────────────── */

export interface ReportSimilarExample {
  category: string;
  similarity: number;
  message: string;
}

export interface ReportCoachResponse {
  explanation: string;
  tips: string[];
  similar_examples: ReportSimilarExample[];
  quiz?: {
    question: string;
    options: string[];
    correct_answer: string;
  } | null;
}

export interface ReportClassification {
  label: string;
  confidence: number;
  explanation: string;
  reason_tags: string[];
}

export interface AnalysisReportData {
  classification: ReportClassification;
  coach_response: ReportCoachResponse;
  /** Optional: whether user guessed correctly */
  was_correct?: boolean | null;
  /** Optional: the user's original guess */
  userGuess?: string | null;
  /** Optional: the raw message text (only shown when showMessage=true) */
  messageText?: string | null;
  /** If false, message text is omitted entirely */
  showMessage?: boolean;
  /** When this analysis was run */
  analysedAt?: Date;
  /** Category from the analysis service, e.g. "fake_bank" */
  category?: string | null;
}

/* ─── Constants ─────────────────────────────────────────────────────────────── */

const MAX_MESSAGE_CHARS = 800;

/* ─── Helper sub-components ─────────────────────────────────────────────────── */

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="report-card" style={{ marginBottom: 16, padding: '14px 16px' }}>
      <h2 style={{ fontSize: 13, fontWeight: 700, textTransform: 'uppercase',
                   letterSpacing: '0.06em', color: '#374151', marginBottom: 10,
                   borderBottom: '1px solid #e5e7eb', paddingBottom: 6 }}>
        {title}
      </h2>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
      <span style={{ fontWeight: 600, fontSize: 12, minWidth: 140, color: '#374151', flexShrink: 0 }}>
        {label}
      </span>
      <span style={{ fontSize: 12, color: '#111111' }}>{value}</span>
    </div>
  );
}

/* ─── Main component ─────────────────────────────────────────────────────────── */

export function AnalysisReport({ data }: { data: AnalysisReportData }) {
  const {
    classification,
    coach_response,
    was_correct,
    userGuess,
    messageText,
    showMessage = true,
    analysedAt,
    category,
  } = data;

  const label = classification.label;
  const confidence = Math.round(classification.confidence * 100);
  const verdictClass = label === 'phishing'
    ? 'verdict-phishing'
    : label === 'safe'
    ? 'verdict-safe'
    : 'verdict-unclear';

  const dateStr = analysedAt
    ? analysedAt.toLocaleString(undefined, {
        year: 'numeric', month: 'long', day: 'numeric',
        hour: '2-digit', minute: '2-digit',
      })
    : new Date().toLocaleString();

  // Truncate long messages
  const displayMessage = messageText
    ? messageText.length > MAX_MESSAGE_CHARS
      ? messageText.slice(0, MAX_MESSAGE_CHARS) + `… [truncated — ${messageText.length} chars total]`
      : messageText
    : null;

  return (
    <div id="threat-iq-report" style={{ fontFamily: 'system-ui, -apple-system, sans-serif',
                                        fontSize: 13, lineHeight: 1.6, color: '#111111',
                                        background: '#ffffff', maxWidth: 720, margin: '0 auto',
                                        padding: '24px 0' }}>

      {/* ── Report header ──────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                    marginBottom: 24, borderBottom: '2px solid #111111', paddingBottom: 12 }}>
        <div>
          <div style={{ fontWeight: 800, fontSize: 20, letterSpacing: '-0.02em' }}>
            ThreatIQ
          </div>
          <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>
            AI Phishing Detection Report
          </div>
        </div>
        <div style={{ textAlign: 'right', fontSize: 11, color: '#6b7280' }}>
          <div>Generated: {dateStr}</div>
          <div style={{ marginTop: 2 }}>Confidential · For personal use only</div>
        </div>
      </div>

      {/* ── Verdict ────────────────────────────────────────────────────────── */}
      <div className={`report-card ${verdictClass}`}
           style={{ padding: '14px 16px', marginBottom: 16 }}>
        <h2 style={{ fontSize: 13, fontWeight: 700, textTransform: 'uppercase',
                     letterSpacing: '0.06em', color: '#374151', marginBottom: 10,
                     borderBottom: '1px solid #e5e7eb', paddingBottom: 6 }}>
          Verdict
        </h2>
        <Row label="Classification" value={
          <strong style={{ fontSize: 14, textTransform: 'capitalize' }}>{label}</strong>
        } />
        <Row label="Confidence" value={`${confidence}%`} />
        {category && (
          <Row label="Category" value={category.replace(/_/g, ' ')} />
        )}
        {userGuess && (
          <Row label="Your prediction" value={
            <>
              <span style={{ textTransform: 'capitalize' }}>{userGuess}</span>
              {was_correct != null && (
                <span style={{ marginLeft: 8, fontWeight: 600,
                               color: was_correct ? '#16a34a' : '#dc2626' }}>
                  {was_correct ? '✓ Correct' : '✗ Incorrect'}
                </span>
              )}
            </>
          } />
        )}
      </div>

      {/* ── AI Explanation ─────────────────────────────────────────────────── */}
      <Section title="AI Explanation">
        <p style={{ fontSize: 13, marginBottom: 10 }}>{classification.explanation}</p>
        {classification.reason_tags.length > 0 && (
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#374151',
                          marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Indicators detected
            </div>
            <div>
              {classification.reason_tags.map((tag) => (
                <span key={tag} className="report-tag">
                  {tag.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          </div>
        )}
      </Section>

      {/* ── Coach Insights ─────────────────────────────────────────────────── */}
      {coach_response.explanation && (
        <Section title="Coach Insights">
          <p style={{ fontSize: 13 }}>{coach_response.explanation}</p>
        </Section>
      )}

      {/* ── Safety Tips ────────────────────────────────────────────────────── */}
      {coach_response.tips.length > 0 && (
        <Section title="Recommended Next Steps">
          <ul style={{ paddingLeft: 18, margin: 0 }}>
            {coach_response.tips.map((tip, i) => (
              <li key={i} style={{ fontSize: 12, marginBottom: 5 }}>{tip}</li>
            ))}
          </ul>
        </Section>
      )}

      {/* ── Similar Examples ───────────────────────────────────────────────── */}
      {coach_response.similar_examples.length > 0 && (
        <Section title="Similar Known Examples">
          {coach_response.similar_examples.map((ex, i) => (
            <div key={i} style={{ marginBottom: 10, paddingBottom: 10,
                                  borderBottom: i < coach_response.similar_examples.length - 1
                                    ? '1px solid #e5e7eb' : 'none' }}>
              <div style={{ display: 'flex', gap: 10, marginBottom: 3, alignItems: 'center' }}>
                <span className="report-tag">{ex.category.replace(/_/g, ' ')}</span>
                <span style={{ fontSize: 11, color: '#6b7280' }}>
                  {Math.round(ex.similarity * 100)}% match
                </span>
              </div>
              <p style={{ fontSize: 11, color: '#4b5563', fontStyle: 'italic',
                          margin: 0, paddingLeft: 2 }}>
                &ldquo;{ex.message.length > 200
                  ? ex.message.slice(0, 200) + '…'
                  : ex.message}&rdquo;
              </p>
            </div>
          ))}
        </Section>
      )}

      {/* ── Analysed message (privacy-gated) ──────────────────────────────── */}
      {showMessage && displayMessage && (
        <Section title="Analysed Message">
          <pre style={{ fontFamily: 'monospace', fontSize: 11, whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word', background: '#f9fafb',
                        border: '1px solid #e5e7eb', borderRadius: 4,
                        padding: '10px 12px', margin: 0, color: '#374151' }}>
            {displayMessage}
          </pre>
        </Section>
      )}

      {/* ── Disclaimer ─────────────────────────────────────────────────────── */}
      <div className="report-disclaimer" style={{ marginTop: 8 }}>
        <strong>Disclaimer:</strong> This report is generated by an AI system and is intended as
        guidance only. It should not be the sole basis for any security decision. Always verify
        suspicious messages through official channels before taking action. ThreatIQ does not
        guarantee the accuracy of AI-generated classifications.
      </div>

    </div>
  );
}
