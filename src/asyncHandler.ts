import type { NextFunction, Request, RequestHandler, Response } from "express";

// Express 4 nao encaminha rejeicoes/excecoes de handlers async para o
// middleware de erro sozinho - sem isso, uma excecao em qualquer rota vira
// uma promise rejeitada sem handler, e o Node mata o processo inteiro
// (unhandledRejection), derrubando TODOS os tenants por causa de uma unica
// requisicao ruim. Envolve o handler para que qualquer erro va para
// next(err) e caia no middleware de erro central (ver server.ts).
export function asyncHandler(
  handler: (req: Request, res: Response, next: NextFunction) => Promise<unknown>
): RequestHandler {
  return (req, res, next) => {
    handler(req, res, next).catch(next);
  };
}
