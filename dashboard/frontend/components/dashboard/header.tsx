"use client";

import { Shield, Sun, Moon, Menu } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ConnectionStatus } from "@/hooks/use-swarm-data";

interface DashboardHeaderProps {
  connectionStatus?: ConnectionStatus;
  isStale?: boolean;
  onOpenMobileMenu?: () => void;
}

export function DashboardHeader({
  connectionStatus,
  isStale,
  onOpenMobileMenu,
}: DashboardHeaderProps) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-border/50">
      <div className="flex h-14 sm:h-16 items-center justify-between px-3.5 sm:px-6">
        <div className="flex items-center gap-2.5 sm:gap-3 group cursor-pointer min-w-0">
          <div className="relative flex items-center justify-center w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-br from-primary to-neon-purple icon-3d neon-glow-cyan flex-shrink-0">
            <Shield className="w-4 h-4 sm:w-5 sm:h-5 text-white" />
            <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-primary to-neon-purple opacity-0 group-hover:opacity-20 transition-opacity" />
          </div>
          <div className="min-w-0">
            <h1 className="text-base sm:text-lg font-bold gradient-text tracking-tight leading-none sm:leading-tight">CDSI</h1>
            <p className="text-[9px] sm:text-[10px] text-muted-foreground font-medium tracking-wider uppercase truncate">
              <span className="hidden sm:inline">Cyber Defense Swarm Intelligence</span>
              <span className="sm:hidden">Swarm Intelligence</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2">
          {/* Live Connection Status Pill */}
          {connectionStatus && (
            <div className="flex items-center gap-1.5 px-2 sm:px-2.5 py-1 rounded-full bg-muted/60 border border-border/50 text-[10px] sm:text-xs">
              <span className="relative flex h-2 w-2 flex-shrink-0">
                <span className={cn(
                  "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
                  connectionStatus === "connected" && "bg-success",
                  (connectionStatus === "connecting" || connectionStatus === "reconnecting") && "bg-amber-500",
                  connectionStatus === "disconnected" && "bg-destructive"
                )} />
                <span className={cn(
                  "relative inline-flex rounded-full h-2 w-2",
                  connectionStatus === "connected" && "bg-success",
                  (connectionStatus === "connecting" || connectionStatus === "reconnecting") && "bg-amber-500",
                  connectionStatus === "disconnected" && "bg-destructive"
                )} />
              </span>
              <span className={cn(
                "font-semibold text-[10px] sm:text-xs",
                connectionStatus === "connected" && "text-success",
                (connectionStatus === "connecting" || connectionStatus === "reconnecting") && "text-amber-500",
                connectionStatus === "disconnected" && "text-destructive"
              )}>
                {connectionStatus === "connected" && "Live"}
                {connectionStatus === "connecting" && "Connecting"}
                {connectionStatus === "reconnecting" && "Reconnecting"}
                {connectionStatus === "disconnected" && "Offline"}
              </span>
              {isStale && (
                <span className="hidden xs:inline text-[9px] px-1 py-0.2 rounded bg-amber-500/15 text-amber-500 font-bold uppercase">
                  Stale
                </span>
              )}
            </div>
          )}

          {/* Theme Switcher */}
          {mounted && (
            <Button
              variant="ghost"
              size="icon"
              className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl hover:bg-primary/5 hover:text-primary transition-all duration-300"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            >
              {theme === "dark" ? (
                <Sun className="w-4 h-4 sm:w-5 sm:h-5 text-warning" />
              ) : (
                <Moon className="w-4 h-4 sm:w-5 sm:h-5 text-primary" />
              )}
            </Button>
          )}

          {/* Mobile Navigation Drawer Trigger */}
          {onOpenMobileMenu && (
            <Button
              variant="ghost"
              size="icon"
              className="lg:hidden w-8 h-8 sm:w-9 sm:h-9 rounded-xl hover:bg-primary/5 hover:text-primary transition-all duration-300"
              onClick={onOpenMobileMenu}
              aria-label="Open Navigation Menu"
            >
              <Menu className="w-4 h-4 sm:w-5 sm:h-5" />
            </Button>
          )}
        </div>
      </div>
    </header>
  );
}

