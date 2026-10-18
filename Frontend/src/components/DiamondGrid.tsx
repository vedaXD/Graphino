import React from "react";

interface DiamondGridProps {
  size?: number; // size of individual diamonds (e.g., 8-10px)
  matrix?: 3 | 4; // 3x3 or 4x4 grid
  color?: "ash" | "white" | "ink" | "dim";
  className?: string;
}

export const DiamondGrid: React.FC<DiamondGridProps> = ({
  size = 8,
  matrix = 3,
  color = "ash",
  className = "",
}) => {
  const count = matrix * matrix;

  const colorClasses = {
    ash: "bg-[#aaaaaa]",
    white: "bg-[#ffffff]",
    ink: "bg-[#181011]",
    dim: "bg-[#666666]",
  };

  return (
    <div
      className={`inline-grid gap-[4px] p-1 ${className}`}
      style={{
        gridTemplateColumns: `repeat(${matrix}, ${size}px)`,
      }}
      aria-hidden="true"
    >
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className={`${colorClasses[color]} rotate-45 transform transition-transform duration-200 hover:scale-125`}
          style={{
            width: `${size}px`,
            height: `${size}px`,
          }}
        />
      ))}
    </div>
  );
};
