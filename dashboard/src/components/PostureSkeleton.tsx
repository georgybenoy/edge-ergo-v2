import React from "react";
import { BodySegments } from "../types/dashboard";

interface PostureSkeletonProps {
  segments?: BodySegments;
  className?: string;
}

const getSegmentColor = (status?: string) => {
  if (!status) return "#39D98A"; // Default safe
  const s = status.toLowerCase();
  if (s.includes("safe") || s.includes("low")) return "#39D98A";
  if (s.includes("attention") || s.includes("moderate")) return "#F2C94C";
  if (s.includes("high risk") || s.includes("high")) return "#FF6B7A";
  if (s.includes("critical") || s.includes("very_high")) return "#FF4D4D";
  return "#39D98A";
};

export const PostureSkeleton: React.FC<PostureSkeletonProps> = ({
  segments,
  className = "",
}) => {
  const neckColor = getSegmentColor(segments?.neck);
  const trunkColor = getSegmentColor(segments?.trunk);
  const shoulderColor = getSegmentColor(segments?.shoulders);
  const wristColor = getSegmentColor(segments?.wrists);
  const legColor = getSegmentColor(segments?.legs);

  return (
    <div
      className={`relative flex flex-col items-center justify-center p-4 rounded-card bg-bg-secondary border border-subtle-border ${className}`}
    >
      <div className="absolute top-3 left-3 flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-brand-accent animate-pulse" />
        <span className="text-caption text-content-secondary uppercase tracking-wider font-semibold">
          Kinematic Skeleton (Non-Camera)
        </span>
      </div>

      <div className="w-full max-w-[240px] aspect-[3/4] my-4 flex items-center justify-center">
        <svg
          viewBox="0 0 200 280"
          className="w-full h-full filter drop-shadow-[0_0_10px_rgba(0,0,0,0.5)]"
          aria-label="Abstract posture wireframe colored by anatomical joint risk"
        >
          {/* Subtle Grid / Target Backdrop */}
          <circle cx="100" cy="140" r="90" stroke="#303030" strokeWidth="1" strokeDasharray="3 3" fill="none" opacity="0.4" />
          <circle cx="100" cy="140" r="50" stroke="#303030" strokeWidth="1" strokeDasharray="2 2" fill="none" opacity="0.3" />

          {/* Spine / Trunk Line */}
          <line x1="100" y1="70" x2="100" y2="160" stroke={trunkColor} strokeWidth="4" strokeLinecap="round" />

          {/* Shoulders Bar */}
          <line x1="60" y1="85" x2="140" y2="85" stroke={shoulderColor} strokeWidth="4" strokeLinecap="round" />

          {/* Left Arm (Upper + Forearm) */}
          <line x1="60" y1="85" x2="40" y2="125" stroke={shoulderColor} strokeWidth="3" strokeLinecap="round" />
          <line x1="40" y1="125" x2="35" y2="160" stroke={wristColor} strokeWidth="3" strokeLinecap="round" />

          {/* Right Arm (Upper + Forearm) */}
          <line x1="140" y1="85" x2="160" y2="125" stroke={shoulderColor} strokeWidth="3" strokeLinecap="round" />
          <line x1="160" y1="125" x2="165" y2="160" stroke={wristColor} strokeWidth="3" strokeLinecap="round" />

          {/* Pelvis / Hips */}
          <line x1="75" y1="160" x2="125" y2="160" stroke={trunkColor} strokeWidth="4" strokeLinecap="round" />

          {/* Left Leg */}
          <line x1="75" y1="160" x2="70" y2="210" stroke={legColor} strokeWidth="3" strokeLinecap="round" />
          <line x1="70" y1="210" x2="68" y2="255" stroke={legColor} strokeWidth="3" strokeLinecap="round" />

          {/* Right Leg */}
          <line x1="125" y1="160" x2="130" y2="210" stroke={legColor} strokeWidth="3" strokeLinecap="round" />
          <line x1="130" y1="210" x2="132" y2="255" stroke={legColor} strokeWidth="3" strokeLinecap="round" />

          {/* Neck Line */}
          <line x1="100" y1="50" x2="100" y2="70" stroke={neckColor} strokeWidth="4" strokeLinecap="round" />

          {/* Head Joint */}
          <circle cx="100" cy="40" r="18" fill="#1D1D1D" stroke={neckColor} strokeWidth="3" />
          <circle cx="100" cy="40" r="5" fill={neckColor} />

          {/* Key Joint Nodes */}
          {/* Shoulders */}
          <circle cx="60" cy="85" r="5" fill={shoulderColor} />
          <circle cx="140" cy="85" r="5" fill={shoulderColor} />

          {/* Elbows */}
          <circle cx="40" cy="125" r="4" fill={shoulderColor} />
          <circle cx="160" cy="125" r="4" fill={shoulderColor} />

          {/* Wrists */}
          <circle cx="35" cy="160" r="4.5" fill={wristColor} />
          <circle cx="165" cy="160" r="4.5" fill={wristColor} />

          {/* Hips */}
          <circle cx="75" cy="160" r="4.5" fill={trunkColor} />
          <circle cx="125" cy="160" r="4.5" fill={trunkColor} />

          {/* Knees */}
          <circle cx="70" cy="210" r="4" fill={legColor} />
          <circle cx="130" cy="210" r="4" fill={legColor} />

          {/* Feet */}
          <circle cx="68" cy="255" r="3.5" fill={legColor} />
          <circle cx="132" cy="255" r="3.5" fill={legColor} />
        </svg>
      </div>

      {/* Anatomy Legend */}
      <div className="w-full grid grid-cols-3 gap-2 pt-2 border-t border-subtle-border/60 text-caption text-center">
        <div className="flex flex-col items-center">
          <span className="text-content-muted">Neck</span>
          <span className="font-medium" style={{ color: neckColor }}>
            {segments?.neck || "Safe"}
          </span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-content-muted">Trunk</span>
          <span className="font-medium" style={{ color: trunkColor }}>
            {segments?.trunk || "Safe"}
          </span>
        </div>
        <div className="flex flex-col items-center">
          <span className="text-content-muted">Wrists</span>
          <span className="font-medium" style={{ color: wristColor }}>
            {segments?.wrists || "Safe"}
          </span>
        </div>
      </div>
    </div>
  );
};
