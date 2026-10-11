"use client";

import { ClipboardList, FileSpreadsheet, Package, Ruler, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { PageHeader } from "@/components/AppShell";
import { Dropzone } from "@/components/Dropzone";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Input";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { useToast } from "@/components/ui/Toast";
import { createJob } from "@/lib/api";
import { DEFAULTS } from "@/lib/constants";
import { errorMessage } from "@/lib/utils";

/**
 * One flow only: drop a drawing → AI + engine read rooms / openings / walls / slabs /
 * members / misc → measurement sheet (IS 1200), BOQ abstract and material requirement.
 * No module selector and no standards: the API defaults `module` to "measurement".
 */
export default function NewMeasurementPage() {
  const router = useRouter();
  const toast = useToast();

  const [projectName, setProjectName] = useState<string>(DEFAULTS.measurement.project_name);
  const [level, setLevel] = useState("");
  const [location, setLocation] = useState("");
  const [files, setFiles] = useState<File[]>([]);

  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = files.length > 0 && projectName.trim().length > 0 && level.trim().length > 0 && !submitting;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    setProgress(0);
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f, f.name));
    fd.append("project_name", projectName.trim());
    fd.append("level", level.trim());
    if (location.trim()) fd.append("location", location.trim());
    try {
      const res = await createJob(fd, (f) => setProgress(Math.round(f * 100)));
      toast.success("Drawing uploaded", "Reading has started — you can watch the pipeline on the job page.");
      router.push(`/jobs/${res.job_id}`);
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
      setProgress(0);
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="New measurement" description="Drop the drawing. You get the measurement sheet, BOQ and material list." />

      <form onSubmit={submit} className="space-y-6">
        {/* 1. Project */}
        <section>
          <StepLabel n={1} title="Project" />
          <Card>
            <CardBody className="grid gap-4 sm:grid-cols-2">
              <Field label="Project name" required className="sm:col-span-2">
                {(id) => <Input id={id} value={projectName} onChange={(e) => setProjectName(e.target.value)} required disabled={submitting} autoComplete="organization" />}
              </Field>
              <Field label="Floor / Level" required hint='e.g. "6th floor"'>
                {(id) => <Input id={id} value={level} onChange={(e) => setLevel(e.target.value)} placeholder="6th floor" required disabled={submitting} />}
              </Field>
              <Field label="Building / Wing" hint="Optional">
                {(id) => <Input id={id} value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Tower A" disabled={submitting} />}
              </Field>
            </CardBody>
          </Card>
        </section>

        {/* 2. Drawing */}
        <section>
          <StepLabel n={2} title="Drawing" hint="DWG preferred. PDF and images are read too." />
          <Dropzone files={files} onFilesChange={setFiles} disabled={submitting} />
        </section>

        {error ? (
          <Alert tone="danger" title="Upload failed">
            {error}
          </Alert>
        ) : null}

        {/* Submit */}
        <Card className="sticky bottom-4 z-20 shadow-pop">
          <CardHeader
            className="border-b-0 py-3"
            title={
              submitting
                ? progress < 100
                  ? `Uploading… ${progress}%`
                  : "Upload complete — starting the reading"
                : files.length
                  ? `${files.length} file${files.length === 1 ? "" : "s"} ready`
                  : "Add a drawing to begin"
            }
            description={
              submitting ? undefined : (
                <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <Deliverable icon={<Ruler />} label="Measurement sheet" />
                  <Deliverable icon={<ClipboardList />} label="BOQ abstract" />
                  <Deliverable icon={<Package />} label="Material list" />
                  <Deliverable icon={<FileSpreadsheet />} label="Excel" />
                </span>
              )
            }
            actions={
              <Button type="submit" size="lg" leftIcon={<Upload />} loading={submitting} disabled={!canSubmit}>
                {submitting ? "Uploading" : "Upload & measure"}
              </Button>
            }
          >
            {submitting ? <ProgressBar value={progress} indeterminate={progress >= 100} className="mt-2 w-full max-w-md" /> : null}
          </CardHeader>
        </Card>
      </form>
    </div>
  );
}

function Deliverable({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-[12.5px] text-muted [&>svg]:size-3.5 [&>svg]:text-brand">
      {icon}
      {label}
    </span>
  );
}

function StepLabel({ n, title, hint }: { n: number; title: string; hint?: string }) {
  return (
    <div className="mb-3 flex items-baseline gap-3">
      <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-ink text-[11.5px] font-bold text-white">{n}</span>
      <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
      {hint ? <span className="text-[12.5px] text-muted">{hint}</span> : null}
    </div>
  );
}
