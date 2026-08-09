import { formatInTimeZone } from "date-fns-tz";
import type { Prisma } from "@prisma/client";

export function formatSlotShort(date: Date, timeZone: string): string {
  return formatInTimeZone(date, timeZone, "dd/MM HH:mm");
}

export function formatPrice(price: Prisma.Decimal | null): string | null {
  if (price === null) return null;
  return price.toNumber().toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
