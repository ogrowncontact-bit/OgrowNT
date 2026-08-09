import { prisma } from "./db";

export async function findOrCreateCustomer(businessId: string, phoneNumber: string, name?: string) {
  return prisma.customer.upsert({
    where: { businessId_phoneNumber: { businessId, phoneNumber } },
    update: name ? { name } : {},
    create: { businessId, phoneNumber, name },
  });
}
