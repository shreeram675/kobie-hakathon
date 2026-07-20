import { type ReactNode } from "react";
import { Logo } from "./Logo";
import { cn } from "@/lib/format";

/** Sticky dark topbar with glass blur backdrop. */
export function Topbar({
  children,
  className,
}: {
  children?: ReactNode;
  className?: string;
}) {
  return (
    <header
      className={cn(
        "glass-bar sticky top-0 z-40 border-b border-white/10",
        className,
      )}
    >
      <div className="flex h-16 w-full items-center justify-between gap-4 px-5">
        <Logo />
        <div className="flex items-center gap-3">{children}</div>
      </div>
    </header>
  );
}
