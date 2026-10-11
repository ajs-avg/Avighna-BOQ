"use client";

import { FileSearch, Info } from "lucide-react";
import { useState } from "react";
import { Chip } from "../ui/Badge";
import { IconButton } from "../ui/Button";
import { Dialog } from "../ui/Dialog";

export interface EvidenceButtonProps {
  evidence: string[];
  sourceSheet?: string | null;
  /** What the evidence is for, e.g. "Wall W1". */
  subject: string;
}

/**
 * "Why did the AI read it this way?" — hover shows the first lines as a tooltip, click opens
 * the full list (a dialog rather than a popover so it is never clipped by the table scroller).
 */
export function EvidenceButton({ evidence, sourceSheet, subject }: EvidenceButtonProps) {
  const [open, setOpen] = useState(false);
  const lines = evidence.filter((l) => l.trim());
  const hasAny = lines.length > 0 || !!sourceSheet;
  if (!hasAny) {
    return <span className="inline-flex size-7 items-center justify-center text-muted/40" title="No evidence recorded" aria-label="No evidence recorded"><Info className="size-3.5" /></span>;
  }
  const tooltip = [sourceSheet ? `Sheet: ${sourceSheet}` : null, ...lines.slice(0, 4), lines.length > 4 ? `+${lines.length - 4} more` : null].filter(Boolean).join("\n");
  return (
    <>
      <IconButton
        label={`Evidence for ${subject}`}
        title={tooltip}
        size="xs"
        className="text-muted hover:text-brand"
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
      >
        <Info />
      </IconButton>
      <Dialog open={open} onClose={() => setOpen(false)} size="md" icon={<FileSearch />} title="Evidence" description={subject}>
        {sourceSheet ? (
          <p className="mb-3 flex items-center gap-2 text-[12.5px] text-muted">
            Source sheet <Chip>{sourceSheet}</Chip>
          </p>
        ) : null}
        {lines.length ? (
          <ol className="space-y-1.5 rounded-lg border border-line bg-surface-2/60 px-3 py-2 font-mono text-[11.5px] leading-5 text-ink/85">
            {lines.map((l, i) => (
              <li key={i} className="break-words">
                {l}
              </li>
            ))}
          </ol>
        ) : (
          <p className="text-[13px] text-muted">No evidence lines were recorded for this row.</p>
        )}
      </Dialog>
    </>
  );
}
