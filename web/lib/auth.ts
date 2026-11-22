import type { NextAuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";

const serverApiUrl = () =>
  process.env.SNIPZO_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

export const authOptions: NextAuthOptions = {
  session: { strategy: "jwt" },
  pages: { signIn: "/login" },
  providers: [
    CredentialsProvider({
      name: "Email",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials.password) return null;
        let response: Response;
        try {
          response = await fetch(`${serverApiUrl()}/auth/login`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({
              email: credentials.email,
              password: credentials.password,
            }),
          });
        } catch {
          throw new Error("SERVICE_UNAVAILABLE");
        }
        if (response.status >= 500) {
          throw new Error("SERVICE_UNAVAILABLE");
        }
        if (!response.ok) return null;
        const data = await response.json();
        return {
          id: data.user.id,
          email: data.user.email,
          name: data.user.name ?? data.user.email,
          plan: data.user.plan,
          accessToken: data.access_token,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = user.accessToken;
        token.plan = user.plan;
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken;
      session.plan = token.plan;
      return session;
    },
  },
};
