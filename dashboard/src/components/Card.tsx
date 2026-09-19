import React from "react";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  variant?: "primary" | "secondary";
  noPadding?: boolean;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = "",
  variant = "primary",
  noPadding = false,
  ...props
}) => {
  const bgClass = variant === "primary" ? "bg-bg-card" : "bg-bg-secondary";
  const paddingClass = noPadding ? "" : "p-4 sm:p-5";

  return (
    <div
      className={`rounded-card border border-subtle-border ${bgClass} ${paddingClass} transition-colors duration-150 ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};
