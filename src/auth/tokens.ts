import jwt from "jsonwebtoken";
import { config } from "../config";

export interface AccessTokenPayload {
  userId: string;
}

export function signAccessToken(payload: AccessTokenPayload): string {
  return jwt.sign(payload, config.jwtSecret, { expiresIn: config.jwtExpiresInSeconds });
}

export function verifyAccessToken(token: string): AccessTokenPayload {
  const decoded = jwt.verify(token, config.jwtSecret);
  if (typeof decoded !== "object" || decoded === null || typeof (decoded as Record<string, unknown>).userId !== "string") {
    throw new Error("Token invalido: payload inesperado.");
  }
  return { userId: (decoded as Record<string, unknown>).userId as string };
}
