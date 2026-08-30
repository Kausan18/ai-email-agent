// Thresholds mirror backend/config.py settings — HIGH_CONFIDENCE_THRESHOLD (0.85)
// and LOW_CONFIDENCE_THRESHOLD (0.50) — kept in sync manually for V1 since
// there's no shared config layer between frontend and backend yet.
const HIGH = 0.85;
const LOW = 0.5;

export function ConfidenceBar({ confidence }: { confidence: number }) {
  const color =
    confidence >= HIGH ? "bg-confidence-high" : confidence >= LOW ? "bg-confidence-mid" : "bg-confidence-low";

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-border">
        <div className={`h-full ${color}`} style={{ width: `${confidence * 100}%` }} />
      </div>
      <span className="font-mono text-[11px] text-textMuted">{Math.round(confidence * 100)}%</span>
    </div>
  );
}