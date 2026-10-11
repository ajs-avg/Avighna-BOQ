import { PencilLine } from "lucide-react";
import { editedByNote } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Small muted "Edited by a@b.com on …" line, rendered only when the row carries the API's edit stamp. */
export function EditedByNote({ evidence, className }: { evidence: string[] | null | undefined; className?: string }) {
  const note = editedByNote(evidence);
  if (!note) return null;
  return (
    <p className={cn("mt-0.5 flex min-w-0 items-center gap-1 text-[11px] leading-4 text-muted", className)} title={note}>
      <PencilLine className="size-3 shrink-0" aria-hidden />
      <span className="truncate">{note}</span>
    </p>
  );
}
