import { prisma, type SupportTicketCategory, type SupportTicketStatus } from "@inner/db";

export interface SupportTicketRow {
  id: string;
  category: SupportTicketCategory;
  email: string;
  message: string;
  status: SupportTicketStatus;
  createdAt: Date;
}

export async function listSupportTickets(status?: SupportTicketStatus, limit = 100): Promise<SupportTicketRow[]> {
  return prisma.supportTicket.findMany({
    where: status ? { status } : undefined,
    orderBy: { createdAt: "desc" },
    take: limit,
  });
}

export async function getOpenSupportTicketCount(): Promise<number> {
  return prisma.supportTicket.count({ where: { status: "open" } });
}
