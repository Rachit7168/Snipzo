import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Snipzo — Turn long videos into vertical Shorts";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          backgroundColor: "#09090b",
          color: "#fafafa",
          padding: "64px",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div
            style={{
              width: "48px",
              height: "48px",
              borderRadius: "12px",
              backgroundColor: "#facc15",
              color: "#09090b",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "28px",
              fontWeight: 900,
            }}
          >
            S
          </div>
          <div style={{ fontSize: "34px", fontWeight: 900, letterSpacing: "-0.02em", display: "flex" }}>
            <span>Snip</span>
            <span style={{ color: "#facc15" }}>zo</span>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "20px", maxWidth: "880px" }}>
          <div
            style={{
              fontSize: "62px",
              fontWeight: 900,
              lineHeight: 1.08,
              letterSpacing: "-0.03em",
              display: "flex",
              flexWrap: "wrap",
            }}
          >
            Turn long videos into vertical Shorts.
          </div>
          <div style={{ fontSize: "26px", color: "#a1a1aa", lineHeight: 1.4 }}>
            AI highlights · Face-tracked 9:16 crop · Word-level captions · Direct YouTube publishing
          </div>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderTop: "1px solid #27272a",
            paddingTop: "24px",
            fontSize: "22px",
            color: "#a1a1aa",
          }}
        >
          <span>Free tier: 3 videos &amp; 30 minutes / month</span>
          <span style={{ color: "#facc15", fontWeight: 700 }}>MP4 · MOV · WebM · YouTube URLs</span>
        </div>
      </div>
    ),
    { ...size }
  );
}
