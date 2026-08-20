import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@inner/db";
import { requireAdmin } from "@/lib/adminAuth";

export interface SearchResult {
  type: string;
  label: string;
  sublabel: string;
  href: string;
}

/** Read-only — every admin role (including analyst/support/viewer) can search. */
export async function GET(request: NextRequest) {
  await requireAdmin();
  const q = request.nextUrl.searchParams.get("q")?.trim();
  if (!q || q.length < 2) return NextResponse.json({ results: [] });

  const [assessments, questions, profiles, users, orders, journalPosts] = await Promise.all([
    prisma.assessment.findMany({
      where: { OR: [{ name: { contains: q, mode: "insensitive" } }, { slug: { contains: q, mode: "insensitive" } }] },
      take: 5,
    }),
    prisma.question.findMany({
      where: { prompt: { contains: q, mode: "insensitive" } },
      take: 5,
      include: { assessmentVersion: { include: { assessment: true } } },
    }),
    prisma.profile.findMany({
      where: { name: { contains: q, mode: "insensitive" } },
      take: 5,
      include: { assessmentVersion: { include: { assessment: true } } },
    }),
    prisma.user.findMany({ where: { email: { contains: q, mode: "insensitive" } }, take: 5 }),
    prisma.order.findMany({
      where: { OR: [{ id: { equals: q } }, { user: { email: { contains: q, mode: "insensitive" } } }] },
      take: 5,
      include: { user: true, price: { include: { assessment: true } } },
    }),
    prisma.journalPost.findMany({
      where: { OR: [{ title: { contains: q, mode: "insensitive" } }, { slug: { contains: q, mode: "insensitive" } }] },
      take: 5,
    }),
  ]);

  const results: SearchResult[] = [
    ...assessments.map((a) => ({ type: "Discovery", label: a.name, sublabel: `/${a.slug}`, href: `/admin/assessments/${a.id}` })),
    ...questions.map((qu) => ({
      type: "Question",
      label: qu.prompt.slice(0, 80),
      sublabel: qu.assessmentVersion.assessment.name,
      href: `/admin/assessments/${qu.assessmentVersion.assessment.id}`,
    })),
    ...profiles.map((p) => ({
      type: "Profile",
      label: p.name,
      sublabel: p.assessmentVersion.assessment.name,
      href: `/admin/assessments/${p.assessmentVersion.assessment.id}`,
    })),
    ...users.map((u) => ({ type: "User", label: u.email, sublabel: "Identity", href: `/admin/users` })),
    ...orders.map((o) => ({
      type: "Order",
      label: o.user.email,
      sublabel: `${o.price.assessment.name} · ${o.status}`,
      href: `/admin/orders`,
    })),
    ...journalPosts.map((j) => ({ type: "Journal", label: j.title, sublabel: `/journal/${j.slug}`, href: `/admin/journal/${j.id}` })),
  ];

  return NextResponse.json({ results });
}
