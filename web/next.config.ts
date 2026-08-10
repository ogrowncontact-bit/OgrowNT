import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // web/ e um app irmao do backend (Express, na raiz do repo), nao um
  // monorepo - fixa a raiz aqui para o Turbopack nao inferir a raiz errada
  // por causa do package-lock.json da raiz do repo.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
