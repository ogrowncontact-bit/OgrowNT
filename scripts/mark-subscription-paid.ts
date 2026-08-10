import { SubscriptionStatus } from "@prisma/client";
import { prisma } from "../src/db";

// CLI de ops: ate existir um processador de pagamento real integrado (ver
// src/billing/errors.ts - POST /subscription/checkout e um stub honesto),
// pagamentos (setup fee, mensalidade) acontecem por fora do sistema
// (Pix/transferencia) e o time confirma manualmente aqui. Nunca finge que
// um pagamento online aconteceu.
//
// Uso:
//   npm run mark-subscription-paid -- --slug barbearia-ze --setup-fee-paid
//   npm run mark-subscription-paid -- --slug barbearia-ze --status ACTIVE

function parseArgs(argv: string[]): Record<string, string | boolean> {
  const args: Record<string, string | boolean> = {};
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (!token.startsWith("--")) continue;
    const key = token.slice(2);
    const next = argv[i + 1];
    if (next !== undefined && !next.startsWith("--")) {
      args[key] = next;
      i++;
    } else {
      args[key] = true;
    }
  }
  return args;
}

function usageAndExit(): never {
  console.error(
    "Uso: npm run mark-subscription-paid -- --slug SLUG-DA-EMPRESA " +
      "[--setup-fee-paid] " +
      `[--status ${Object.values(SubscriptionStatus).join("|")}]`
  );
  process.exit(1);
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const slug = args.slug as string | undefined;
  if (!slug) usageAndExit();

  const status = args.status as string | undefined;
  if (status && !Object.values(SubscriptionStatus).includes(status as SubscriptionStatus)) {
    console.error(`--status invalido. Valores aceitos: ${Object.values(SubscriptionStatus).join(", ")}`);
    process.exit(1);
  }

  const business = await prisma.business.findUnique({ where: { slug } });
  if (!business) {
    console.error(`Nenhuma empresa encontrada com slug "${slug}".`);
    process.exit(1);
  }

  const subscription = await prisma.subscription.findUnique({ where: { businessId: business.id } });
  if (!subscription) {
    console.error(`A empresa "${slug}" nao tem uma assinatura (Subscription) ainda.`);
    process.exit(1);
  }

  const updated = await prisma.subscription.update({
    where: { businessId: business.id },
    data: {
      ...(args["setup-fee-paid"] ? { setupFeePaid: true } : {}),
      ...(status ? { status: status as SubscriptionStatus } : {}),
    },
    include: { plan: true },
  });

  console.log(`Assinatura de "${slug}" atualizada:`);
  console.log(`  plano:        ${updated.plan.name}`);
  console.log(`  status:       ${updated.status}`);
  console.log(`  setupFeePaid: ${updated.setupFeePaid}`);
}

main()
  .catch((err) => {
    console.error(err);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
