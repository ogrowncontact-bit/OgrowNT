// Compartilhado entre o registro via API (src/routes/auth.routes.ts) e o CLI
// de bootstrap (scripts/create-business.ts) - as duas formas de criar uma
// empresa devem gerar slugs da mesma maneira.
export function slugify(input: string): string {
  return input
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 60);
}
