export class ChannelNotImplementedError extends Error {
  constructor(channel: string, action: string) {
    super(`${action} ainda nao esta disponivel para o canal ${channel} nesta versao.`);
    this.name = "ChannelNotImplementedError";
  }
}
