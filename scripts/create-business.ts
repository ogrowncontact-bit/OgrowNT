import { BusinessIndustry } from "@prisma/client";
import { hashPassword } from "../src/auth/passwords";
import { encryptSecret } from "../src/crypto";
import { prisma } from "../src/db";

// CLI de bootstrap/ops: cadastra uma empresa (tenant), opcionalmente conecta um
// numero de WhatsApp, cria dados de demonstracao e (opcionalmente) um dono
// logavel. O fluxo real de cadastro de uma empresa nova e
// POST /api/auth/register; este script existe para testes end-to-end rapidos
// e para tarefas que a API ainda nao cobre (conectar WhatsApp).
//
// Uso:
//   npm run create-business -- --name "Barbearia do Ze" --industry OTHER \
//     --owner-email dono@example.com --owner-password "senha-forte-123" --seed-demo
//
//   npm run create-business -- --name "Sunset Horse Riding" --industry EQUESTRIAN \
//     --phone-number-id 123456789 --waba-id 987654321 --access-token EAAB...

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
    'Uso: npm run create-business -- --name "Barbearia do Ze" --industry OTHER ' +
      `(valores: ${Object.values(BusinessIndustry).join(", ")}) ` +
      "[--slug barbearia-ze] [--timezone America/Sao_Paulo] " +
      "[--owner-email EMAIL --owner-password SENHA] " +
      "[--phone-number-id ID] [--waba-id ID] [--access-token TOKEN] [--verified-name NOME] " +
      "[--seed-demo]"
  );
  process.exit(1);
}

function slugify(input: string): string {
  return input
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 60);
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const name = args.name as string | undefined;
  const industry = args.industry as string | undefined;

  if (!name || !industry) usageAndExit();
  if (!Object.values(BusinessIndustry).includes(industry as BusinessIndustry)) {
    console.error(`industry invalido. Valores aceitos: ${Object.values(BusinessIndustry).join(", ")}`);
    process.exit(1);
  }

  const slug = (args.slug as string) || slugify(name);

  const business = await prisma.business.create({
    data: {
      name,
      slug,
      industry: industry as BusinessIndustry,
      timezone: (args.timezone as string) || "America/Sao_Paulo",
    },
  });

  const ownerEmail = args["owner-email"] as string | undefined;
  const ownerPassword = args["owner-password"] as string | undefined;
  if (ownerEmail) {
    if (!ownerPassword || ownerPassword.length < 8) {
      console.error("--owner-password precisa ter pelo menos 8 caracteres quando --owner-email e informado.");
      process.exit(1);
    }
    const normalizedEmail = ownerEmail.trim().toLowerCase();
    const owner = await prisma.user.upsert({
      where: { email: normalizedEmail },
      update: {},
      create: { email: normalizedEmail, passwordHash: await hashPassword(ownerPassword), name },
    });
    await prisma.membership.create({
      data: { userId: owner.id, businessId: business.id, role: "OWNER" },
    });
    console.log(`Dono cadastrado: ${normalizedEmail} (faca login em POST /api/auth/login).`);
  }

  const phoneNumberId = args["phone-number-id"] as string | undefined;
  if (phoneNumberId) {
    await prisma.whatsAppAccount.create({
      data: {
        businessId: business.id,
        phoneNumberId,
        wabaId: (args["waba-id"] as string) || "",
        verifiedName: (args["verified-name"] as string) || undefined,
        encryptedAccessToken: encryptSecret((args["access-token"] as string) || ""),
      },
    });
  }

  if (args["seed-demo"]) {
    const service = await prisma.service.create({
      data: { businessId: business.id, name: "Corte de cabelo", durationMinutes: 30, price: 50 },
    });
    await prisma.service.create({
      data: { businessId: business.id, name: "Barba", durationMinutes: 20, price: 30 },
    });
    for (let weekday = 1; weekday <= 5; weekday++) {
      await prisma.businessHours.create({
        data: { businessId: business.id, weekday, openTime: "09:00", closeTime: "18:00" },
      });
    }
    console.log(`Servicos e horarios de demonstracao criados (servico exemplo: ${service.id}).`);
  }

  console.log("\nEmpresa criada com sucesso!");
  console.log(`  id:       ${business.id}`);
  console.log(`  slug:     ${business.slug}`);
  console.log(`  industry: ${business.industry}`);

  if (!phoneNumberId) {
    console.log(
      "\nNenhum WhatsApp conectado ainda - o bot vai rodar em modo dry-run (mensagens aparecem no log do servidor)."
    );
    console.log("Para conectar de verdade, rode de novo com --phone-number-id, --waba-id e --access-token.");
  }
}

main()
  .catch((err) => {
    console.error(err);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
