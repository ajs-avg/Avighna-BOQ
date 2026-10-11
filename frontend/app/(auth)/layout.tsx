import { CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";
import { Logo, ProductTag } from "@/components/Logo";
import { TAGLINE } from "@/lib/constants";

const POINTS = [
  "Drop DWG, DXF, PDF or scanned drawings — several at once.",
  "Structural drawings become a bar bending schedule in tons.",
  "Interior fit-out drawings become a BOQ in m², lm and nos.",
  "Review, correct, approve and download the Excel sheet.",
];

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden overflow-hidden bg-gradient-to-br from-brand via-brand to-brand-dark text-white lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div
          className="pointer-events-none absolute -right-32 -top-32 size-[480px] rounded-full bg-white/10 blur-3xl"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute -bottom-40 -left-24 size-[420px] rounded-full bg-ink/20 blur-3xl"
          aria-hidden
        />
        <div className="relative flex items-center gap-3">
          <span className="inline-flex rounded-md bg-white px-2 py-1.5">
            <Logo height={22} href={null} />
          </span>
          <ProductTag className="bg-white/15 text-white" />
        </div>
        <div className="relative max-w-lg">
          <h1 className="text-[40px] font-semibold leading-[1.1] tracking-tight">{TAGLINE}</h1>
          <p className="mt-4 text-[15px] leading-6 text-white/85">
            The Avighna measurement cockpit. Upload construction drawings, let the engine read and quantify them, then review
            and approve the Excel measurement sheet.
          </p>
          <ul className="mt-8 space-y-3">
            {POINTS.map((p) => (
              <li key={p} className="flex items-start gap-3 text-[14px] text-white/90">
                <CheckCircle2 className="mt-0.5 size-[18px] shrink-0 text-white" />
                {p}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-[12px] text-white/70">© {new Date().getFullYear()} Avighna Group · Internal tool</p>
      </section>

      <section className="flex flex-col items-center justify-center bg-surface px-4 py-10 sm:px-8">
        <div className="mb-8 flex items-center gap-3 lg:hidden">
          <Logo height={28} href={null} priority />
          <ProductTag />
        </div>
        <div className="card w-full max-w-[420px] overflow-hidden animate-pop-in">
          <div className="h-1.5 bg-brand" aria-hidden />
          <div className="p-7 sm:p-8">{children}</div>
        </div>
        <p className="mt-6 text-center text-[12px] text-muted">Avighna BOQ · Internal measurement platform</p>
      </section>
    </div>
  );
}
