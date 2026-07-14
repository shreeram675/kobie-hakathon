"use client";

import { useState } from "react";
import { FileJson, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  runId: string;
  programName?: string | null;
  size?: "sm" | "md" | "lg";
  variant?: "primary" | "secondary" | "ghost" | "outline";
  className?: string;
}

export function DownloadJSONButton({ runId, programName, size = "sm", variant = "outline", className }: Props) {
  const [loading, setLoading] = useState(false);

  const handleDownload = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/run/${runId}/export?download=true`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const blob = await res.blob();

      const today = new Date().toISOString().slice(0, 10);
      const name = (programName ?? runId)
        .replace(/[^\w\s-]/g, "")
        .replace(/\s+/g, "_")
        .slice(0, 40);
      const fileName = `Export_${name}_${today}.json`;

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("JSON export failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Button
      size={size}
      variant={variant}
      onClick={handleDownload}
      disabled={loading}
      className={className}
    >
      {loading ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        <FileJson className="h-3.5 w-3.5" />
      )}
      {loading ? "Preparing JSON…" : "Download JSON"}
    </Button>
  );
}
