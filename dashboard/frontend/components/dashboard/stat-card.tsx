import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface StatCardProps {
  title: string;
  value: string | number;
  change?: string;
  changeType?: "positive" | "negative" | "neutral";
  icon: LucideIcon;
  iconColor?: string;
}

export function StatCard({
  title,
  value,
  change,
  changeType = "neutral",
  icon: Icon,
  iconColor = "text-primary",
}: StatCardProps) {
  return (
    <div className="card-3d neon-border p-5 group cursor-default">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{title}</p>
          <p className="mt-2 text-3xl font-bold text-card-foreground tracking-tight">{value}</p>
          {change && (
            <p
              className={cn(
                "mt-1.5 text-xs font-medium",
                changeType === "positive" && "text-success",
                changeType === "negative" && "text-destructive",
                changeType === "neutral" && "text-muted-foreground"
              )}
            >
              {changeType === "positive" && "● "}
              {changeType === "negative" && "▲ "}
              {change}
            </p>
          )}
        </div>
        <div className={cn(
          "p-3 rounded-xl icon-3d transition-all duration-300",
          iconColor === "text-primary" && "bg-primary/8 group-hover:bg-primary/15 group-hover:neon-glow-cyan",
          iconColor === "text-destructive" && "bg-destructive/8 group-hover:bg-destructive/15 group-hover:neon-glow-red",
          iconColor === "text-success" && "bg-success/8 group-hover:bg-success/15 group-hover:neon-glow-green",
          iconColor === "text-warning" && "bg-warning/8 group-hover:bg-warning/15",
          iconColor
        )}>
          <Icon className="w-5 h-5 transition-transform duration-300 group-hover:scale-110" />
        </div>
      </div>
    </div>
  );
}
