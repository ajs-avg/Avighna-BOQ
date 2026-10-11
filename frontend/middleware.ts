import { NextResponse, type NextRequest } from "next/server";

/**
 * Route guard. The JWT itself lives in localStorage (see lib/auth.ts); the
 * `avighna_token` cookie is a mirror set at login so the edge can redirect
 * unauthenticated visitors to /login before any page renders. Token validity
 * is still enforced by the API (401 → lib/api.ts clears the session).
 */
const TOKEN_COOKIE = "avighna_token";
const PUBLIC_PATHS = ["/login", "/set-password"];

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

export function middleware(req: NextRequest) {
  const { pathname, search } = req.nextUrl;
  const token = req.cookies.get(TOKEN_COOKIE)?.value;

  if (!token && !isPublic(pathname)) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    const next = `${pathname}${search}`;
    if (next !== "/") url.searchParams.set("next", next);
    return NextResponse.redirect(url);
  }

  if (token && pathname === "/login") {
    const url = req.nextUrl.clone();
    url.pathname = "/";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Everything except Next internals, static assets and files with an extension.
     */
    "/((?!_next/static|_next/image|favicon.ico|brand/|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|txt|xml|json|woff2?)$).*)",
  ],
};
