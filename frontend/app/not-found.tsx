import { Logo } from "@/components/Logo";
import { ButtonLink } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-5 bg-surface p-6 text-center">
      <Logo height={28} href={null} />
      <div>
        <p className="text-[12px] font-semibold uppercase tracking-[0.1em] text-brand">404</p>
        <h1 className="mt-1 text-[22px] font-semibold tracking-tight text-ink">Page not found</h1>
        <p className="mt-1 text-[13.5px] text-muted">The page you are looking for does not exist or has moved.</p>
      </div>
      <ButtonLink href="/">Back to dashboard</ButtonLink>
    </div>
  );
}
