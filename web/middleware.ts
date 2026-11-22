export { default } from "next-auth/middleware";

// Public marketing pages (/ and /pricing), auth pages, and legal pages stay open.
export const config = {
  matcher: [
    "/projects",
    "/projects/:path*",
    "/billing",
    "/billing/:path*",
    "/channels",
    "/channels/:path*",
  ],
};
