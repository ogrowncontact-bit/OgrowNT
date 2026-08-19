/** The one place amountCents+currency becomes a display string — never hardcode a currency symbol next to a formatted amount elsewhere. */
export function formatPrice(amountCents: number, currency: string = "EUR"): string {
  return new Intl.NumberFormat("en-IE", { style: "currency", currency }).format(amountCents / 100);
}
