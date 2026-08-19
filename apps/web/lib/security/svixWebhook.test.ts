import { createHmac } from "node:crypto";
import { describe, expect, it } from "vitest";
import { verifySvixSignature } from "./svixWebhook";

const SECRET = "whsec_" + Buffer.from("test-secret-bytes-1234").toString("base64");

function sign(svixId: string, svixTimestamp: string, rawBody: string): string {
  const secretBytes = Buffer.from(SECRET.replace(/^whsec_/, ""), "base64");
  const signedContent = `${svixId}.${svixTimestamp}.${rawBody}`;
  const sig = createHmac("sha256", secretBytes).update(signedContent).digest("base64");
  return `v1,${sig}`;
}

describe("verifySvixSignature", () => {
  it("accepts a correctly signed payload", () => {
    const svixId = "msg_1";
    const svixTimestamp = String(Math.floor(Date.now() / 1000));
    const rawBody = '{"type":"email.delivered"}';
    const svixSignature = sign(svixId, svixTimestamp, rawBody);

    expect(verifySvixSignature({ secret: SECRET, svixId, svixTimestamp, svixSignature, rawBody })).toBe(true);
  });

  it("rejects a tampered body", () => {
    const svixId = "msg_1";
    const svixTimestamp = String(Math.floor(Date.now() / 1000));
    const svixSignature = sign(svixId, svixTimestamp, '{"type":"email.delivered"}');

    expect(
      verifySvixSignature({ secret: SECRET, svixId, svixTimestamp, svixSignature, rawBody: '{"type":"email.bounced"}' })
    ).toBe(false);
  });

  it("rejects a stale timestamp outside the tolerance window", () => {
    const svixId = "msg_1";
    const staleTimestamp = String(Math.floor(Date.now() / 1000) - 10 * 60); // 10 minutes ago
    const rawBody = '{"type":"email.delivered"}';
    const svixSignature = sign(svixId, staleTimestamp, rawBody);

    expect(verifySvixSignature({ secret: SECRET, svixId, svixTimestamp: staleTimestamp, svixSignature, rawBody })).toBe(false);
  });

  it("rejects when headers are missing", () => {
    expect(
      verifySvixSignature({ secret: SECRET, svixId: null, svixTimestamp: "123", svixSignature: "v1,abc", rawBody: "{}" })
    ).toBe(false);
  });

  it("rejects a signature signed with the wrong secret", () => {
    const svixId = "msg_1";
    const svixTimestamp = String(Math.floor(Date.now() / 1000));
    const rawBody = "{}";
    const wrongSecret = "whsec_" + Buffer.from("a-completely-different-secret").toString("base64");
    const secretBytes = Buffer.from(wrongSecret.replace(/^whsec_/, ""), "base64");
    const wrongSig = `v1,${createHmac("sha256", secretBytes).update(`${svixId}.${svixTimestamp}.${rawBody}`).digest("base64")}`;

    expect(verifySvixSignature({ secret: SECRET, svixId, svixTimestamp, svixSignature: wrongSig, rawBody })).toBe(false);
  });
});
