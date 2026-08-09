import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";
import { config } from "./config";

const ALGORITHM = "aes-256-gcm";
const IV_LENGTH = 12;

function getKey(): Buffer {
  const key = Buffer.from(config.masterEncryptionKey, "hex");
  if (key.length !== 32) {
    throw new Error(
      "MASTER_ENCRYPTION_KEY invalida: precisa ser uma string hex de 32 bytes (64 caracteres). Gere com: openssl rand -hex 32"
    );
  }
  return key;
}

// Usado para guardar tokens de acesso do WhatsApp de cada empresa no banco sem
// expo-los em texto puro. Formato do resultado: "<iv>:<authTag>:<ciphertext>" em hex.
export function encryptSecret(plainText: string): string {
  const iv = randomBytes(IV_LENGTH);
  const cipher = createCipheriv(ALGORITHM, getKey(), iv);
  const encrypted = Buffer.concat([cipher.update(plainText, "utf8"), cipher.final()]);
  const authTag = cipher.getAuthTag();
  return `${iv.toString("hex")}:${authTag.toString("hex")}:${encrypted.toString("hex")}`;
}

export function decryptSecret(payload: string): string {
  const parts = payload.split(":");
  if (parts.length !== 3) {
    throw new Error("Payload criptografado em formato invalido");
  }
  const [ivHex, authTagHex, dataHex] = parts;
  if (!ivHex || !authTagHex) {
    throw new Error("Payload criptografado em formato invalido");
  }
  const decipher = createDecipheriv(ALGORITHM, getKey(), Buffer.from(ivHex, "hex"));
  decipher.setAuthTag(Buffer.from(authTagHex, "hex"));
  const decrypted = Buffer.concat([
    decipher.update(Buffer.from(dataHex, "hex")),
    decipher.final(),
  ]);
  return decrypted.toString("utf8");
}
