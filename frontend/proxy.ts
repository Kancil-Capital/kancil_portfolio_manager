import { createServerClient } from "@supabase/ssr";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL ?? "",
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "",
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (cookiesToSet) => {
          cookiesToSet.forEach(({ name, value, options }) => {
            response.cookies.set(name, value, options);
          });
        },
      },
    }
  );

  // Always call getUser() early so token refresh cookies are written to response.
  const { data: { user } } = await supabase.auth.getUser();

  const isAuthPage = pathname.startsWith("/login");

  if (!user && !isAuthPage) {
    // Unauthenticated — redirect to login
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (user && isAuthPage) {
    // Already authenticated — skip login page
    return NextResponse.redirect(new URL("/research", request.url));
  }

  return response;
}

export const config = {
  matcher: [
    // Run on all paths except Next.js internals and static assets
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
