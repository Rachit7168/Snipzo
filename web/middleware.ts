export { default } from "next-auth/middleware";

// Everything except sign-in, registration, legal pages, and static assets needs a session.
export const config = {
  matcher: ["/", "/projects/:path*", "/billing/:path*", "/channels/:path*"],
};
