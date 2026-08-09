import { encryptSecret } from "../src/crypto";
import { prisma } from "../src/db";

// CLI de bootstrap: cadastra uma empresa (tenant) e, opcionalmente, conecta um
// numero de WhatsApp e cria dados de demonstracao. Existe porque a Fase 1
// ainda nao tem um dashboard web - isso e o "onboarding" de uma empresa nova.
//
// Uso:
//   npm run create-business -- --name "Barbearia do Ze" --slug barbearia-ze
//   npm run create-business -- --name "Barbearia do Ze" --slug barbearia-ze \
//     --phone-number-id 123456789 --waba-id 987654321 --access-token EAAB... \
//     --seed-demo

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

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  const name = args.name as string | undefined;
  const slug = args.slug as string | undefined;

  if (!name || !slug) {
    console.error(
      'Uso: npm run create-business -- --name "Barbearia do Ze" --slug barbearia-ze ' +
        "[--timezone America/Sao_Paulo] [--phone-number-id ID] [--waba-id ID] " +
        "[--access-token TOKEN] [--verified-name NOME] [--seed-demo]"
    );
    process.exit(1);
  }

  const business = await prisma.business.create({
    data: {
      name,
      slug,
      timezone: (args.timezone as string) || "America/Sao_Paulo",
    },
  });

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
  console.log(`  id:     ${business.id}`);
  console.log(`  slug:   ${business.slug}`);
  console.log(`  apiKey: ${business.apiKey}  <- use como "Authorization: Bearer <apiKey>" na API /api/*`);

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
