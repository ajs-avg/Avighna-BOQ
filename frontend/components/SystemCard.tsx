"use client";

import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { getSystem } from "@/lib/api";
import { formatInt, formatMb } from "@/lib/format";
import type { SystemInfo } from "@/lib/types";
import { cn, errorMessage } from "@/lib/utils";
import { Alert } from "./ui/Alert";
import { Button, IconButton } from "./ui/Button";
import { Card, CardBody, CardHeader } from "./ui/Card";
import { SkeletonText } from "./ui/Skeleton";

/** Compact status card for GET /api/v1/system: version, AI, DWG converters, storage and limits. */
export function SystemCard({ className }: { className?: string }) {
  const [info, setInfo] = useState<SystemInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      setInfo(await getSystem());
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const aiModels = info ? [info.ai.model_fast, info.ai.model_pro].filter((m): m is string => !!m) : [];

  return (
    <Card className={className}>
      <CardHeader
        title="System"
        description={info ? `Avighna BOQ v${info.version}` : "Backend, AI and converter status."}
        className="py-3"
        actions={
          <IconButton label="Refresh system status" size="xs" onClick={() => void load()} loading={refreshing && info !== null}>
            <RefreshCw />
          </IconButton>
        }
      />
      <CardBody className="py-3">
        {error && !info ? (
          <Alert tone="danger" title="Could not load system status" actions={<Button size="xs" variant="secondary" onClick={() => void load()}>Retry</Button>}>
            {error}
          </Alert>
        ) : !info ? (
          <SkeletonText lines={6} />
        ) : (
          <dl className="space-y-2 text-[12.5px]">
            <Row label="AI">
              <StatusDot on={info.ai.enabled} />
              <span className="min-w-0 truncate" title={info.ai.message || undefined}>
                {info.ai.enabled ? (aiModels.length ? aiModels.join(" · ") : info.ai.provider || "on") : "off"}
              </span>
            </Row>
            <Row label="LibreDWG" sub={<code className="block truncate font-mono text-[11px] text-muted" title={info.libredwg_bin}>{info.libredwg_bin || "—"}</code>}>
              <StatusDot on={info.converters.libredwg} />
              <span>{info.converters.libredwg ? "on" : "off"}</span>
            </Row>
            <Row label="ODA">
              <StatusDot on={info.converters.oda} />
              <span>{info.converters.oda ? "on" : "off"}</span>
            </Row>
            <Row label="Database">
              <span className="tnum" title={info.db_path}>
                {formatMb(info.db_mb)}
              </span>
            </Row>
            <Row label="Data folder">
              <span className="tnum" title={info.data_dir}>
                {formatMb(info.data_mb)}
              </span>
            </Row>
            <Row label="Workers">
              <span className="tnum">
                {formatInt(info.worker_threads)} thread{info.worker_threads === 1 ? "" : "s"}
              </span>
            </Row>
            <Row label="Max upload">
              <span className="tnum">{formatInt(info.max_upload_mb)} MB</span>
            </Row>
            <Row label="Users">
              <span className="tnum">{formatInt(info.users)}</span>
            </Row>
          </dl>
        )}
        {error && info ? <p className="mt-3 text-[11.5px] text-danger">Refresh failed: {error}</p> : null}
      </CardBody>
    </Card>
  );
}

function StatusDot({ on }: { on: boolean }) {
  return (
    <span
      className={cn("inline-block size-2 shrink-0 rounded-full", on ? "bg-success" : "bg-brand")}
      role="img"
      aria-label={on ? "on" : "off"}
    />
  );
}

function Row({ label, sub, children }: { label: string; sub?: ReactNode; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[88px_1fr] gap-2">
      <dt className="text-muted">{label}</dt>
      <dd className="min-w-0 text-ink">
        <span className="flex min-w-0 items-center gap-2">{children}</span>
        {sub}
      </dd>
    </div>
  );
}
