"use client";

import { useState } from "react";
import { Button } from "@inner/ui";

interface ShareResultButtonProps {
  shareTitle: string;
  shareText: string;
}

/** Never shares raw answers or dimension scores — only the already-resolved profile-name copy passed in from the server. */
export function ShareResultButton({ shareTitle, shareText }: ShareResultButtonProps) {
  const [copied, setCopied] = useState(false);

  async function handleShare() {
    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share({ title: shareTitle, text: shareText });
        return;
      } catch {
        // user cancelled the native share sheet, or it's unsupported for this content — fall through to clipboard
      }
    }
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      await navigator.clipboard.writeText(shareText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <Button variant="ghost" onClick={handleShare} className="!w-auto px-0">
      {copied ? "Copied to clipboard" : "Share my result"}
    </Button>
  );
}
