"use client";

import { Lock, RotateCcw, Save, Sliders } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/AppShell";
import { StandardsForm } from "@/components/StandardsForm";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { SkeletonText } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { getStandards, putStandards } from "@/lib/api";
import type { Standards } from "@/lib/types";
import { useUser } from "@/lib/user-context";
import { errorMessage } from "@/lib/utils";

export default function StandardsPage() {
  const { isAdmin } = useUser();
  const toast = useToast();
  const [saved, setSaved] = useState<Standards | null>(null);
  const [draft, setDraft] = useState<Standards | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const s = await getStandards();
      setSaved(s);
      setDraft(s);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const dirty = !!draft && !!saved && JSON.stringify(draft) !== JSON.stringify(saved);

  const save = async () => {
    if (!draft) return;
    setSaving(true);
    try {
      const s = await putStandards(draft);
      setSaved(s);
      setDraft(s);
      toast.success("Standards saved", "New jobs will use these constants. Existing jobs keep theirs until recalculated.");
    } catch (err) {
      toast.error("Could not save standards", errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Company standards"
        description="BBS constants that drive every cut-length and weight formula. Jobs snapshot these at creation."
        actions={
          isAdmin ? (
            <>
              <Button variant="secondary" leftIcon={<RotateCcw />} disabled={!dirty || saving} onClick={() => setDraft(saved)}>
                Discard changes
              </Button>
              <Button leftIcon={<Save />} loading={saving} disabled={!dirty} onClick={() => void save()}>
                Save standards
              </Button>
            </>
          ) : (
            <Badge tone="neutral" icon={<Lock />} size="md">
              Read-only — admins can edit
            </Badge>
          )
        }
      />

      {error ? (
        <Alert tone="danger" title="Could not load standards" className="mb-6" actions={<Button size="sm" variant="secondary" onClick={() => void load()}>Retry</Button>}>
          {error}
        </Alert>
      ) : null}

      <Card>
        <CardHeader icon={<Sliders />} title="Bar bending schedule constants" description="Defaults reproduce the Avighna 14th-floor measurement sheet exactly (Ld = 39d, covers 30 / 20 / 40 mm, bend deduction 0.6d per corner)." />
        <CardBody>
          {draft ? (
            <StandardsForm value={draft} onChange={setDraft} readOnly={!isAdmin} />
          ) : (
            <div className="space-y-6">
              <SkeletonText lines={4} />
              <SkeletonText lines={4} />
            </div>
          )}
        </CardBody>
        {isAdmin && dirty ? (
          <div className="sticky bottom-4 mx-5 mb-5 flex items-center justify-between rounded-xl border border-brand/30 bg-brand-tint px-4 py-3 shadow-pop animate-pop-in">
            <p className="text-[13px] text-ink">You have unsaved changes.</p>
            <div className="flex gap-2">
              <Button variant="secondary" size="sm" onClick={() => setDraft(saved)} disabled={saving}>
                Discard
              </Button>
              <Button size="sm" leftIcon={<Save />} loading={saving} onClick={() => void save()}>
                Save
              </Button>
            </div>
          </div>
        ) : null}
      </Card>
    </div>
  );
}
