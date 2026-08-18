import { ImageResponse } from "next/og";
import { getAssessmentConfig } from "@/lib/assessments";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const config = await getAssessmentConfig(slug);
  const name = config?.name ?? "INNER";
  const hook = config?.hook ?? "Discover what makes you, you.";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          backgroundColor: "#faf6ef",
          color: "#1c1a17",
        }}
      >
        <div style={{ display: "flex", fontSize: 28, letterSpacing: 6, color: "#635c4e", fontWeight: 600 }}>
          INNER
        </div>
        <div style={{ display: "flex", marginTop: 28, fontSize: 64, fontFamily: "serif", lineHeight: 1.15 }}>
          {name}
        </div>
        <div style={{ display: "flex", marginTop: 32, fontSize: 32, color: "#4a453d", lineHeight: 1.4, maxWidth: 900 }}>
          {hook}
        </div>
      </div>
    ),
    { ...size }
  );
}
