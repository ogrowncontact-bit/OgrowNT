import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { prisma } from "@inner/db";
import { signSessionToken, verifySessionToken } from "./security/sessionToken";

export const ADMIN_COOKIE = "inner_admin_session";
const ADMIN_SESSION_MAX_AGE_SECONDS = 60 * 60 * 12; // 12 hours — re-login rather than an indefinite stateless session

export type AdminRole = "owner" | "editor" | "viewer" | "founder" | "admin" | "content_editor" | "support" | "analyst";

export interface AdminSession {
  id: string;
  email: string;
  role: AdminRole;
}

/**
 * FASE 25 role prep: 5 named roles (founder/admin/content_editor/support/
 * analyst) exist alongside the original owner/editor/viewer, but there's no
 * per-resource ACL — every write route already trusts one coarse
 * read/write gate (requireAdmin vs requireAdminWriter), so each new role
 * maps onto whichever side of that gate it belongs on. Building real
 * per-resource permissions would mean auditing every one of the ~30
 * existing write routes individually; that's a distinct, larger piece of
 * work than "prepare roles" asks for.
 */
const READ_ONLY_ROLES = new Set<AdminRole>(["viewer", "support", "analyst"]);

export const ADMIN_ROLE_LABELS: Record<AdminRole, string> = {
  owner: "Owner",
  editor: "Editor",
  viewer: "Viewer",
  founder: "Founder",
  admin: "Admin",
  content_editor: "Content Editor",
  support: "Support",
  analyst: "Analyst",
};

/** Route-handler-only (sets a cookie). Verifies credentials and starts a signed admin session. */
export async function loginAdmin(email: string, password: string): Promise<AdminSession | null> {
  const { verifyPassword } = await import("./security/password");
  const user = await prisma.adminUser.findUnique({ where: { email: email.toLowerCase().trim() } });
  if (!user || !verifyPassword(password, user.passwordHash)) return null;

  const jar = await cookies();
  jar.set(ADMIN_COOKIE, signSessionToken(user.id), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: ADMIN_SESSION_MAX_AGE_SECONDS,
  });

  return { id: user.id, email: user.email, role: user.role };
}

export async function logoutAdmin(): Promise<void> {
  const jar = await cookies();
  jar.delete(ADMIN_COOKIE);
}

/** Safe to call from a Server Component render (no cookie mutation) — returns null rather than redirecting. */
export async function getAdminSession(): Promise<AdminSession | null> {
  const jar = await cookies();
  const adminId = verifySessionToken(jar.get(ADMIN_COOKIE)?.value);
  if (!adminId) return null;

  const user = await prisma.adminUser.findUnique({ where: { id: adminId } });
  if (!user) return null;

  return { id: user.id, email: user.email, role: user.role };
}

/** For pages that must be authenticated — redirects to login rather than returning null. */
export async function requireAdmin(): Promise<AdminSession> {
  const session = await getAdminSession();
  if (!session) redirect("/admin/login");
  return session;
}

/** For pages/actions that need write access — read-only roles can view but never mutate. */
export async function requireAdminWriter(): Promise<AdminSession> {
  const session = await requireAdmin();
  if (READ_ONLY_ROLES.has(session.role)) redirect("/admin");
  return session;
}
