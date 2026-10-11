"use client";

import { RefreshCw, ScrollText } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { adminAudit } from "@/lib/api";
import { formatDate, formatRelative } from "@/lib/format";
import type { AuditEntry } from "@/lib/types";
import { cn, errorMessage } from "@/lib/utils";
import { Alert } from "./ui/Alert";
import { Chip } from "./ui/Badge";
import { Button, IconButton } from "./ui/Button";
import { Card, CardHeader } from "./ui/Card";
import { EmptyState } from "./ui/EmptyState";
import { EmptyRow, SkeletonRows, Table, TableWrap } from "./ui/Table";

export const AUDIT_LIMIT = 100;

/** Admin audit trail: the latest `AUDIT_LIMIT` entries from GET /api/v1/admin/audit, newest first. */
export function AuditLogCard({ className }: { className?: string }) {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [loadedAt, setLoadedAt] = useState<Date | null>(null);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const res = await adminAudit(AUDIT_LIMIT);
      setEntries(res.items);
      setLoadedAt(new Date());
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
      setEntries((prev) => prev ?? []);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader
        title="Audit log"
        icon={<ScrollText />}
        description={
          entries === null
            ? `Latest ${AUDIT_LIMIT} sensitive actions: sign-ins, edits, approvals, user and standards changes.`
            : `Latest ${AUDIT_LIMIT} sensitive actions${loadedAt ? ` · refreshed ${formatRelative(loadedAt)}` : ""}.`
        }
        actions={
          <IconButton label="Refresh audit log" size="sm" variant="secondary" onClick={() => void load()} loading={refreshing}>
            <RefreshCw />
          </IconButton>
        }
      />
      {error ? (
        <div className="px-5 pt-4">
          <Alert tone="danger" title="Could not load the audit log" actions={<Button size="sm" variant="secondary" onClick={() => void load()}>Retry</Button>}>
            {error}
          </Alert>
        </div>
      ) : null}
      <TableWrap flush maxHeight={520}>
        <Table>
          <thead>
            <tr>
              <th className="w-40">Time</th>
              <th>User</th>
              <th>Action</th>
              <th>Target</th>
              <th className="min-w-[240px]">Detail</th>
            </tr>
          </thead>
          <tbody>
            {entries === null ? (
              <SkeletonRows rows={6} cols={5} />
            ) : entries.length === 0 ? (
              <EmptyRow colSpan={5}>
                <EmptyState compact icon={<ScrollText />} title="No audit entries yet" description="Actions appear here as people sign in, edit, approve and manage users." />
              </EmptyRow>
            ) : (
              entries.map((e) => (
                <tr key={e.id}>
                  <td className="tnum whitespace-nowrap text-[12.5px] text-muted" title={e.at}>
                    {formatDate(e.at)}
                  </td>
                  <td className="max-w-[200px] truncate text-[12.5px]" title={e.user_email ?? undefined}>
                    {e.user_email || <span className="text-muted/60">—</span>}
                  </td>
                  <td>
                    <Chip>{e.action}</Chip>
                  </td>
                  <td className="max-w-[180px] truncate font-mono text-[11.5px] text-muted" title={e.target ?? undefined}>
                    {e.target || <span className="font-sans text-muted/60">—</span>}
                  </td>
                  <td className="max-w-[420px] truncate text-[12.5px] text-ink/85" title={e.detail ?? undefined}>
                    {e.detail || <span className="text-muted/60">—</span>}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </Table>
      </TableWrap>
    </Card>
  );
}
