"use client";

import { Armchair, Check, ChevronDown, Layers, Sliders, Upload } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";
import { PageHeader } from "@/components/AppShell";
import { Dropzone } from "@/components/Dropzone";
import { StandardsForm } from "@/components/StandardsForm";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Input";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { Select } from "@/components/ui/Select";
import { SkeletonText } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { createJob, getStandards } from "@/lib/api";
import { CURRENCIES, DEFAULTS, MODULE_META } from "@/lib/constants";
import type { Module, Standards } from "@/lib/types";
import { cn, errorMessage } from "@/lib/utils";

export default function NewMeasurementPage() {
  return (
    <Suspense fallback={<NewMeasurementForm initialModule={null} />}>
      <NewMeasurementWithParams />
    </Suspense>
  );
}

function NewMeasurementWithParams() {
  const params = useSearchParams();
  const m = params.get("module");
  return <NewMeasurementForm initialModule={m === "structural" || m === "fitout" ? m : null} />;
}

function NewMeasurementForm({ initialModule }: { initialModule: Module | null }) {
  const router = useRouter();
  const toast = useToast();

  const [module, setModule] = useState<Module | null>(initialModule);
  const [files, setFiles] = useState<File[]>([]);

  // structural
  const [projectS, setProjectS] = useState<string>(DEFAULTS.structural.project_name);
  const [levelS, setLevelS] = useState("");
  const [contractorS, setContractorS] = useState<string>(DEFAULTS.structural.contractor);
  const [drawnBy, setDrawnBy] = useState("");
  const [standards, setStandards] = useState<Standards | null>(null);
  const [standardsDefault, setStandardsDefault] = useState<Standards | null>(null);
  const [standardsError, setStandardsError] = useState<string | null>(null);
  const [standardsOpen, setStandardsOpen] = useState(false);

  // fit-out
  const [projectF, setProjectF] = useState<string>(DEFAULTS.fitout.project_name);
  const [locationF, setLocationF] = useState<string>(DEFAULTS.fitout.location);
  const [levelF, setLevelF] = useState("");
  const [currency, setCurrency] = useState<string>(DEFAULTS.fitout.currency);
  const [contractorF, setContractorF] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getStandards()
      .then((s) => {
        if (cancelled) return;
        setStandards(s);
        setStandardsDefault(s);
      })
      .catch((err) => {
        if (!cancelled) setStandardsError(errorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const standardsDirty = !!standards && !!standardsDefault && JSON.stringify(standards) !== JSON.stringify(standardsDefault);

  const projectName = module === "fitout" ? projectF : projectS;
  const level = module === "fitout" ? levelF : levelS;
  const canSubmit = !!module && files.length > 0 && projectName.trim().length > 0 && level.trim().length > 0 && !submitting;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!module || !canSubmit) return;
    setSubmitting(true);
    setError(null);
    setProgress(0);
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f, f.name));
    fd.append("module", module);
    fd.append("project_name", projectName.trim());
    fd.append("level", level.trim());
    if (module === "structural") {
      if (contractorS.trim()) fd.append("contractor", contractorS.trim());
      if (drawnBy.trim()) fd.append("drawn_by", drawnBy.trim());
      if (standards && standardsDirty) fd.append("standards", JSON.stringify(standards));
    } else {
      if (contractorF.trim()) fd.append("contractor", contractorF.trim());
      if (locationF.trim()) fd.append("location", locationF.trim());
      fd.append("currency", currency);
    }
    try {
      const res = await createJob(fd, (f) => setProgress(Math.round(f * 100)));
      toast.success("Drawings uploaded", "Processing has started — you can watch the pipeline on the job page.");
      router.push(`/jobs/${res.job_id}`);
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
      setProgress(0);
    }
  };

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="New measurement" description="Pick a module, drop the drawings, confirm the job details." />

      <form onSubmit={submit} className="space-y-6">
        {/* 1. Module */}
        <section>
          <StepLabel n={1} title="What are we measuring?" />
          <div className="grid gap-4 sm:grid-cols-2">
            <ModuleCard
              module="structural"
              selected={module === "structural"}
              onSelect={() => setModule("structural")}
              icon={<Layers />}
              disabled={submitting}
            />
            <ModuleCard module="fitout" selected={module === "fitout"} onSelect={() => setModule("fitout")} icon={<Armchair />} disabled={submitting} />
          </div>
        </section>

        {/* 2. Drawings */}
        <section className={cn("transition-opacity", !module && "pointer-events-none opacity-40")}>
          <StepLabel n={2} title="Drawings" hint="DWG preferred. PDF and images are read too." />
          <Dropzone files={files} onFilesChange={setFiles} disabled={!module || submitting} />
        </section>

        {/* 3. Details */}
        <section className={cn("transition-opacity", !module && "pointer-events-none opacity-40")}>
          <StepLabel n={3} title="Job details" />
          <Card>
            <CardBody className="grid gap-4 sm:grid-cols-2">
              {module === "fitout" ? (
                <>
                  <Field label="Project name" required className="sm:col-span-2">
                    {(id) => <Input id={id} value={projectF} onChange={(e) => setProjectF(e.target.value)} required disabled={submitting} />}
                  </Field>
                  <Field label="Location">{(id) => <Input id={id} value={locationF} onChange={(e) => setLocationF(e.target.value)} disabled={submitting} />}</Field>
                  <Field label="Level / area" required hint='e.g. "Ground floor — Sales lounge"'>
                    {(id) => <Input id={id} value={levelF} onChange={(e) => setLevelF(e.target.value)} placeholder="Ground floor" required disabled={submitting} />}
                  </Field>
                  <Field label="Currency" required>
                    {(id) => (
                      <Select id={id} value={currency} onChange={(e) => setCurrency(e.target.value)} disabled={submitting} options={CURRENCIES.map((c) => ({ value: c, label: c }))} />
                    )}
                  </Field>
                  <Field label="Contractor">{(id) => <Input id={id} value={contractorF} onChange={(e) => setContractorF(e.target.value)} placeholder="Optional" disabled={submitting} />}</Field>
                </>
              ) : (
                <>
                  <Field label="Project name" required className="sm:col-span-2">
                    {(id) => <Input id={id} value={projectS} onChange={(e) => setProjectS(e.target.value)} required disabled={submitting} />}
                  </Field>
                  <Field label="Level" required hint='e.g. "14th Floor"'>
                    {(id) => <Input id={id} value={levelS} onChange={(e) => setLevelS(e.target.value)} placeholder="14th Floor" required disabled={submitting} />}
                  </Field>
                  <Field label="Contractor">{(id) => <Input id={id} value={contractorS} onChange={(e) => setContractorS(e.target.value)} disabled={submitting} />}</Field>
                  <Field label="Drawn by">{(id) => <Input id={id} value={drawnBy} onChange={(e) => setDrawnBy(e.target.value)} placeholder="Optional" disabled={submitting} />}</Field>
                </>
              )}
            </CardBody>
          </Card>
        </section>

        {/* 4. Standards (structural) */}
        {module === "structural" ? (
          <section>
            <StepLabel n={4} title="Standards" hint="Pre-filled from company standards. Override for this job only." optional />
            <Card>
              <button
                type="button"
                onClick={() => setStandardsOpen((v) => !v)}
                aria-expanded={standardsOpen}
                className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-surface-2/60"
              >
                <span className="inline-flex size-8 items-center justify-center rounded-lg bg-brand-soft text-brand">
                  <Sliders className="size-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[14px] font-semibold text-ink">BBS constants for this job</span>
                  <span className="block text-[12.5px] text-muted">
                    {standards
                      ? `Ld ${standards.ld_factor}d · covers ${standards.cover_beam_mm}/${standards.cover_slab_mm}/${standards.cover_column_mm} mm · bend deduction ${standards.bend_deduction_d}d`
                      : standardsError
                        ? "Could not load standards — backend defaults will be used"
                        : "Loading…"}
                    {standardsDirty ? <span className="ml-2 font-medium text-brand">· modified</span> : null}
                  </span>
                </span>
                <ChevronDown className={cn("size-4 text-muted transition-transform", standardsOpen && "rotate-180")} />
              </button>
              {standardsOpen ? (
                <CardBody className="border-t border-line">
                  {standards ? (
                    <>
                      <StandardsForm value={standards} onChange={setStandards} compact readOnly={submitting} />
                      {standardsDirty ? (
                        <div className="mt-4 flex justify-end">
                          <Button variant="secondary" size="sm" onClick={() => setStandards(standardsDefault)} disabled={submitting}>
                            Reset to company standards
                          </Button>
                        </div>
                      ) : null}
                    </>
                  ) : standardsError ? (
                    <Alert tone="warning">{standardsError}</Alert>
                  ) : (
                    <SkeletonText lines={5} />
                  )}
                </CardBody>
              ) : null}
            </Card>
          </section>
        ) : null}

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
              submitting ? (
                <span className="flex items-center gap-2">
                  {progress < 100 ? `Uploading… ${progress}%` : "Upload complete — starting the pipeline"}
                </span>
              ) : module ? (
                `${MODULE_META[module].output} · ${files.length} file${files.length === 1 ? "" : "s"}`
              ) : (
                "Select a module to begin"
              )
            }
            description={submitting ? undefined : module ? `Output in ${MODULE_META[module].unit}.` : undefined}
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

function StepLabel({ n, title, hint, optional }: { n: number; title: string; hint?: string; optional?: boolean }) {
  return (
    <div className="mb-3 flex items-baseline gap-3">
      <span className="inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-ink text-[11.5px] font-bold text-white">{n}</span>
      <h2 className="text-[15px] font-semibold text-ink">
        {title}
        {optional ? <span className="ml-1.5 text-[12px] font-normal text-muted">(optional)</span> : null}
      </h2>
      {hint ? <span className="text-[12.5px] text-muted">{hint}</span> : null}
    </div>
  );
}

function ModuleCard({
  module,
  selected,
  onSelect,
  icon,
  disabled,
}: {
  module: Module;
  selected: boolean;
  onSelect: () => void;
  icon: React.ReactNode;
  disabled?: boolean;
}) {
  const meta = MODULE_META[module];
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      disabled={disabled}
      onClick={onSelect}
      className={cn(
        "card group relative flex items-start gap-4 p-5 text-left transition-all",
        selected ? "border-brand ring-2 ring-brand/25 shadow-pop" : "hover:border-line-strong hover:shadow-pop",
        disabled && "cursor-not-allowed opacity-70",
      )}
    >
      <span
        className={cn(
          "inline-flex size-11 shrink-0 items-center justify-center rounded-xl transition-colors [&>svg]:size-5",
          selected ? "bg-brand text-white" : "bg-surface-2 text-ink group-hover:bg-brand-soft group-hover:text-brand",
        )}
      >
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[15px] font-semibold text-ink">{meta.label}</span>
        <span className="mt-1 block text-[12.5px] leading-5 text-muted">{meta.description}</span>
      </span>
      <span
        className={cn(
          "absolute right-4 top-4 inline-flex size-5 items-center justify-center rounded-full border transition-colors",
          selected ? "border-brand bg-brand text-white" : "border-line-strong bg-surface",
        )}
        aria-hidden
      >
        {selected ? <Check className="size-3" strokeWidth={3} /> : null}
      </span>
    </button>
  );
}
