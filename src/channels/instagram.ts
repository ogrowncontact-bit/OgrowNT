import { ChannelNotImplementedError } from "./errors";
import type { ChannelAdapter } from "./types";

// Stub HONESTO, nao uma simulacao: a integracao real com Instagram Direct
// (Graph API de Instagram Messaging) ainda nao foi construida nesta versao
// (ver README - "Instagram" no roadmap, recurso premium futuro). Este
// adapter existe para provar que a arquitetura ja comporta um novo canal sem
// tocar na logica de conversa/IA (src/conversation, src/ai); qualquer
// tentativa de uso lanca um erro claro em vez de fingir que enviou algo.
export function createInstagramAdapter(): ChannelAdapter {
  function notImplemented(action: string): never {
    throw new ChannelNotImplementedError("Instagram", action);
  }

  return {
    type: "INSTAGRAM",
    async sendText() {
      notImplemented("Envio de mensagens de texto");
    },
    async sendList() {
      notImplemented("Envio de listas");
    },
    async sendButtons() {
      notImplemented("Envio de botoes");
    },
    async sendTemplate() {
      notImplemented("Envio de templates");
    },
  };
}
