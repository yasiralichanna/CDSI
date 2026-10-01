"use client";

import { Shield, Sun, Moon } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

export function DashboardHeader() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-border/50">
      <div className="flex h-16 items-center justify-between px-6">
        <div className="flex items-center gap-3 group cursor-pointer">
          <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-neon-purple icon-3d neon-glow-cyan">
            <Shield className="w-5 h-5 text-white" />
            <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-primary to-neon-purple opacity-0 group-hover:opacity-20 transition-opacity" />
          </div>
          <div>
            <h1 className="text-lg font-bold gradient-text tracking-tight">CDSI</h1>
            <p className="text-[10px] text-muted-foreground font-medium tracking-wider uppercase">Cyber Defense Swarm Intelligence</p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          {mounted && (
            <Button
              variant="ghost"
              size="icon"
              className="rounded-xl hover:bg-primary/5 hover:text-primary transition-all duration-300 hover:scale-105"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            >
              {theme === "dark" ? (
                <Sun className="w-5 h-5 text-warning" />
              ) : (
                <Moon className="w-5 h-5 text-primary" />
              )}
            </Button>
          )}
        </div>
      </div>
    </header>
  );
}
