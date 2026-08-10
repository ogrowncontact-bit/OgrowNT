export class BillingNotImplementedError extends Error {
  constructor(action: string) {
    super(
      `${action} ainda nao esta disponivel nesta versao - nao ha processador de pagamento online integrado. ` +
        "Entre em contato com o time para pagar manualmente (Pix/transferencia); seu acesso continua funcionando " +
        "normalmente durante o periodo de teste."
    );
    this.name = "BillingNotImplementedError";
  }
}
