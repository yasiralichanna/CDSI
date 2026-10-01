"use client";

import { Shield, Sun, Moon, Settings, Server, Check, RefreshCw } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getApiBase } from "@/hooks/use-swarm-data";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

export function DashboardHeader() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [backendUrl, setBackendUrl] = useState("");
  const [currentActiveUrl, setCurrentActiveUrl] = useState("");
  const [savedSuccess, setSavedSuccess] = useState(false);

  useEffect(() => {
    setMounted(true);
    const url = getApiBase();
    setCurrentActiveUrl(url);
    const custom = localStorage.getItem("CDSI_BACKEND_URL");
    setBackendUrl(custom || "");
  }, []);

  const handleSave = () => {
    if (backendUrl.trim()) {
      localStorage.setItem("CDSI_BACKEND_URL", backendUrl.trim());
    } else {
      localStorage.removeItem("CDSI_BACKEND_URL");
    }
    window.dispatchEvent(new Event("cdsi_backend_url_changed"));
    setCurrentActiveUrl(getApiBase());
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 2000);
    setIsSettingsOpen(false);
  };

  const handleReset = () => {
    localStorage.removeItem("CDSI_BACKEND_URL");
    setBackendUrl("");
    window.dispatchEvent(new Event("cdsi_backend_url_changed"));
    setCurrentActiveUrl(getApiBase());
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 2000);
    setIsSettingsOpen(false);
  };

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
            <>
              <Button
                variant="ghost"
                size="icon"
                className="rounded-xl hover:bg-primary/5 hover:text-primary transition-all duration-300 hover:scale-105"
                onClick={() => {
                  const custom = localStorage.getItem("CDSI_BACKEND_URL");
                  setBackendUrl(custom || "");
                  setCurrentActiveUrl(getApiBase());
                  setIsSettingsOpen(true);
                }}
                title="Backend Connection Settings"
              >
                <Settings className="w-5 h-5 text-muted-foreground hover:text-primary transition-colors" />
              </Button>

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
            </>
          )}
        </div>
      </div>

      <Dialog open={isSettingsOpen} onOpenChange={setIsSettingsOpen}>
        <DialogContent className="glass-panel border-border/50 sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-foreground">
              <Server className="w-5 h-5 text-primary" />
              Backend Connection Settings
            </DialogTitle>
            <DialogDescription className="text-muted-foreground text-xs mt-1">
              Configure the API server endpoint for CDSI Swarm Intelligence.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="p-3 rounded-xl bg-muted/40 border border-border/50 space-y-1">
              <span className="text-[11px] font-medium text-muted-foreground block">Currently Active Endpoint:</span>
              <span className="text-xs font-mono font-semibold text-primary break-all">{currentActiveUrl}</span>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-foreground">Custom Backend URL (Render / Local):</label>
              <Input
                placeholder="https://cdsi-backend.onrender.com"
                value={backendUrl}
                onChange={(e) => setBackendUrl(e.target.value)}
                className="font-mono text-xs"
              />
              <p className="text-[11px] text-muted-foreground">
                Leave empty to use automatic host detection or build-time environment variable.
              </p>
            </div>
          </div>

          <DialogFooter className="flex flex-row justify-between sm:justify-between items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleReset}
              className="text-xs flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Reset to Auto
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              className="text-xs bg-primary text-primary-foreground hover:bg-primary/90 flex items-center gap-1.5"
            >
              {savedSuccess ? <Check className="w-3.5 h-3.5" /> : null}
              {savedSuccess ? "Saved!" : "Save & Reconnect"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </header>
  );
}
