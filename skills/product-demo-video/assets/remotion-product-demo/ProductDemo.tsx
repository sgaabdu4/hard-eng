import React, {CSSProperties} from "react";
import {
  AbsoluteFill,
  Img,
  Video,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type {DemoDesign, DemoDevice, DemoEvent, DemoScene, ProductDemoProps} from "./demo-types";

const FALLBACK_COLORS = {
  paper: "oklch(99% 0.003 130)",
  surface: "oklch(97% 0.005 130)",
  line: "oklch(86% 0.012 130)",
  ink: "oklch(18% 0.017 138)",
  muted: "oklch(35% 0.018 138)",
  accent: "oklch(34% 0.105 158)",
  accentSoft: "oklch(92% 0.04 155)",
};

const SYSTEM_STACK = "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif";

export function ProductDemo({captureSrc, posterSrc, design, scenes, events}: ProductDemoProps) {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const scene = activeScene(scenes, frame);
  const colors = palette(design);
  const camera = cameraState(scene, events, frame, fps);
  const cursor = cursorState(events, frame, fps, width, height);
  const enter = spring({
    frame: frame - scene.startFrame,
    fps,
    config: {damping: 22, stiffness: 120, mass: 0.8},
  });

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(180deg, ${colors.paper}, ${colors.surface})`,
        color: colors.ink,
        fontFamily: uiStack(design),
        overflow: "hidden",
      }}
    >
      <div style={stageWash(colors)} />
      <CaptionRail
        colors={colors}
        design={design}
        scene={scene}
        scenes={scenes}
        progress={enter}
      />
      <DeviceStage
        captureSrc={captureSrc}
        posterSrc={posterSrc}
        colors={colors}
        scene={scene}
        camera={camera}
      />
      <CursorOverlay cursor={cursor} colors={colors} />
      <div style={{position: "absolute", left: 0, right: 0, bottom: 0, height: 8, background: colors.accent}} />
    </AbsoluteFill>
  );
}

function CaptionRail({
  colors,
  design,
  scene,
  scenes,
  progress,
}: {
  colors: ReturnType<typeof palette>;
  design: DemoDesign;
  scene: DemoScene;
  scenes: DemoScene[];
  progress: number;
}) {
  const index = Math.max(0, scenes.findIndex((item) => item.id === scene.id));
  const total = Math.max(1, scenes.length);
  const titleY = interpolate(progress, [0, 1], [14, 0]);

  return (
    <section
      style={{
        position: "absolute",
        left: 58,
        top: 44,
        width: 520,
        height: 812,
        zIndex: 2,
        display: "flex",
        flexDirection: "column",
        padding: "30px 0 32px",
        borderTop: `1px solid ${colors.line}`,
        borderBottom: `1px solid ${colors.line}`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 48,
          fontFamily: displayStack(design),
          fontSize: 26,
          fontWeight: 800,
          letterSpacing: 0,
        }}
      >
        <span
          style={{
            width: 14,
            height: 14,
            borderRadius: 999,
            background: colors.accent,
            boxShadow: `0 0 0 7px ${colors.accentSoft}`,
          }}
        />
        <span>{design.name}</span>
      </div>

      <div
        style={{
          width: "max-content",
          padding: "8px 10px",
          border: `1px solid ${colors.line}`,
          borderRadius: 999,
          background: colors.paper,
          color: colors.accent,
          fontFamily: displayStack(design),
          fontSize: 15,
          fontWeight: 800,
          lineHeight: 1,
        }}
      >
        {String(index + 1).padStart(2, "0")} / {String(total).padStart(2, "0")}
      </div>

      <h1
        style={{
          margin: "22px 0 0",
          maxWidth: 470,
          fontFamily: displayStack(design),
          fontSize: 62,
          fontWeight: 800,
          lineHeight: 0.98,
          letterSpacing: 0,
          textWrap: "balance",
          opacity: progress,
          transform: `translateY(${titleY}px)`,
        } as CSSProperties}
      >
        {scene.title}
      </h1>

      <p
        style={{
          width: 456,
          margin: "22px 0 0",
          color: colors.muted,
          fontSize: 24,
          fontWeight: 700,
          lineHeight: 1.24,
          textWrap: "pretty",
        } as CSSProperties}
      >
        {scene.copy}
      </p>

      {scene.proof ? (
        <p
          style={{
            width: 456,
            marginTop: 34,
            padding: "18px 18px 19px",
            border: `1px solid ${colors.line}`,
            borderRadius: 8,
            background: colors.paper,
            color: colors.ink,
            fontSize: 19,
            fontWeight: 700,
            lineHeight: 1.32,
          }}
        >
          {scene.proof}
        </p>
      ) : null}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${total}, 1fr)`,
          gap: 7,
          width: 456,
          marginTop: "auto",
        }}
      >
        {scenes.map((item, itemIndex) => (
          <span
            key={item.id}
            style={{
              height: 6,
              borderRadius: 999,
              background: itemIndex <= index ? colors.accent : colors.line,
              transform: itemIndex <= index ? "scaleY(1.75)" : "scaleY(1)",
            }}
          />
        ))}
      </div>
    </section>
  );
}

function DeviceStage({
  captureSrc,
  posterSrc,
  colors,
  scene,
  camera,
}: {
  captureSrc: string;
  posterSrc?: string;
  colors: ReturnType<typeof palette>;
  scene: DemoScene;
  camera: {scale: number; panX: number; panY: number};
}) {
  const device: DemoDevice = scene.device ?? "phone";
  const desktop = device === "desktop";
  const shellStyle = desktop ? desktopFrame(colors, camera) : phoneFrame(colors, camera);
  const screenStyle = desktop ? desktopScreen(colors) : phoneScreen();
  const media = mediaSource(captureSrc);
  const poster = posterSrc ? mediaSource(posterSrc) : undefined;
  const isImage = /\.(png|jpe?g|webp|avif)$/i.test(captureSrc);

  return (
    <section
      style={{
        position: "absolute",
        top: desktop ? 126 : 24,
        right: desktop ? 24 : 64,
        width: desktop ? 956 : 500,
        height: desktop ? 650 : 852,
        zIndex: 3,
        display: "grid",
        placeItems: "center",
      }}
    >
      <div style={shellStyle}>
        {desktop ? <DesktopChrome colors={colors} /> : <PhoneIsland />}
        <div style={screenStyle}>
          {isImage ? (
            <Img src={media} style={mediaStyle} />
          ) : (
            <Video src={media} poster={poster} muted style={mediaStyle} />
          )}
        </div>
      </div>
    </section>
  );
}

function CursorOverlay({
  cursor,
  colors,
}: {
  cursor: {x: number; y: number; active: boolean; clicked: boolean};
  colors: ReturnType<typeof palette>;
}) {
  return (
    <>
      {cursor.clicked ? (
        <div
          style={{
            position: "absolute",
            left: cursor.x - 8,
            top: cursor.y - 8,
            width: 16,
            height: 16,
            borderRadius: 999,
            border: `1.5px solid ${colors.accent}`,
            boxShadow: `0 0 0 8px color-mix(in srgb, ${colors.accent} 16%, transparent), 0 0 36px color-mix(in srgb, ${colors.accent} 30%, transparent)`,
            opacity: 0.7,
          }}
        />
      ) : null}
      <div
        style={{
          position: "absolute",
          left: cursor.x - 21,
          top: cursor.y - 13,
          width: 23,
          height: 27,
          filter: "drop-shadow(0 5px 8px rgba(17, 17, 17, 0.32))",
          opacity: cursor.active ? 1 : 0,
        }}
      >
        <svg viewBox="0 0 24 28" width="23" height="27" style={{transform: "rotate(-7deg)", transformOrigin: "92% 50%"}}>
          <path
            fill="#050505"
            d="M4.1 3.2C2.6 2.1 .8 3.2 .8 5.1v17.8c0 1.9 2.1 3 3.7 1.8l17.2-9.9c1.6-.9 1.6-3.2 0-4.1L4.1 3.2Z"
          />
        </svg>
      </div>
    </>
  );
}

function DesktopChrome({colors}: {colors: ReturnType<typeof palette>}) {
  return (
    <>
      <div style={{position: "absolute", top: 22, left: 24, display: "flex", gap: 12}}>
        {["oklch(62% 0.22 28)", "oklch(72% 0.17 82)", "oklch(60% 0.15 150)"].map((color) => (
          <span key={color} style={{width: 11, height: 11, borderRadius: 999, background: color}} />
        ))}
      </div>
      <div
        style={{
          position: "absolute",
          top: 16,
          left: 98,
          width: 732,
          height: 24,
          borderRadius: 999,
          background: "rgba(255, 255, 255, 0.74)",
          boxShadow: `inset 0 0 0 1px ${colors.line}`,
        }}
      />
    </>
  );
}

function PhoneIsland() {
  return (
    <div
      style={{
        position: "absolute",
        top: 20,
        left: "50%",
        zIndex: 5,
        width: 118,
        height: 33,
        borderRadius: 999,
        background: "#070807",
        transform: "translateX(-50%)",
        boxShadow: "inset 0 -1px 0 rgba(255, 255, 255, 0.08)",
      }}
    />
  );
}

function activeScene(scenes: DemoScene[], frame: number) {
  const sorted = [...scenes].sort((a, b) => a.startFrame - b.startFrame);
  return (
    [...sorted]
      .reverse()
      .find((scene) => frame >= scene.startFrame) ??
    sorted[0] ?? {
      id: "demo",
      startFrame: 0,
      durationFrames: 180,
      title: "Product demo",
      copy: "Add scenes to story.sample.ts.",
    }
  );
}

function cameraState(scene: DemoScene, events: DemoEvent[], frame: number, fps: number) {
  const zooms = events
    .filter((event) => event.type === "zoom" && Number(event.scale ?? 1) > 1)
    .map((event) => ({
      ...event,
      frame: Math.round(((event.t ?? event.atMs ?? 0) / 1000) * fps),
      durationFrames: event.durationFrames ?? 45,
    }))
    .filter((event) => frame >= event.frame && frame <= event.frame + event.durationFrames)
    .sort((a, b) => b.frame - a.frame);

  const event = zooms[0];
  const target = event
    ? {scale: Number(event.scale ?? 1), panX: Number(event.panX ?? 0), panY: Number(event.panY ?? 0)}
    : scene.camera ?? {scale: 1, panX: 0, panY: 0};
  const progress = event
    ? interpolate(frame - event.frame, [0, 14], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})
    : 1;

  return {
    scale: interpolate(progress, [0, 1], [1, target.scale]),
    panX: interpolate(progress, [0, 1], [0, target.panX ?? 0]),
    panY: interpolate(progress, [0, 1], [0, target.panY ?? 0]),
  };
}

function cursorState(events: DemoEvent[], frame: number, fps: number, width: number, height: number) {
  const cursorEvents = events
    .filter((event) => typeof event.x === "number" && typeof event.y === "number")
    .map((event) => ({...event, frame: Math.round(((event.t ?? event.atMs ?? 0) / 1000) * fps)}))
    .filter((event) => event.frame <= frame)
    .sort((a, b) => b.frame - a.frame);

  const current = cursorEvents[0];
  return {
    x: Number(current?.x ?? width * 0.72),
    y: Number(current?.y ?? height * 0.82),
    active: Boolean(current),
    clicked: current?.type === "click" && frame - current.frame < 10,
  };
}

function palette(design: DemoDesign) {
  const colors = design.colors ?? {};
  return {
    paper: colors["color-neutral-0"] ?? FALLBACK_COLORS.paper,
    surface: colors["color-neutral-1"] ?? FALLBACK_COLORS.surface,
    line: colors["color-neutral-3"] ?? FALLBACK_COLORS.line,
    ink: colors["color-ink-1"] ?? FALLBACK_COLORS.ink,
    muted: colors["color-ink-2"] ?? FALLBACK_COLORS.muted,
    accent: colors["color-green-6"] ?? colors["color-accent-1"] ?? FALLBACK_COLORS.accent,
    accentSoft: colors["color-green-1"] ?? colors["color-accent-2"] ?? FALLBACK_COLORS.accentSoft,
  };
}

function uiStack(design: DemoDesign) {
  return design.typography?.uiStack ?? SYSTEM_STACK;
}

function displayStack(design: DemoDesign) {
  return design.typography?.displayStack ?? design.typography?.uiStack ?? SYSTEM_STACK;
}

function mediaSource(src: string) {
  if (/^(https?:|data:|\/)/.test(src)) return src;
  return staticFile(src);
}

function stageWash(colors: ReturnType<typeof palette>): CSSProperties {
  return {
    position: "absolute",
    inset: 0,
    background: `linear-gradient(90deg, rgba(255, 255, 255, 0.82) 0, rgba(255, 255, 255, 0.82) 43%, transparent 43%), linear-gradient(180deg, transparent 0, transparent 78%, color-mix(in srgb, ${colors.accent} 8%, transparent) 100%)`,
  };
}

function phoneFrame(colors: ReturnType<typeof palette>, camera: {scale: number; panX: number; panY: number}): CSSProperties {
  return {
    position: "relative",
    width: 424,
    height: 852,
    padding: 16,
    borderRadius: 50,
    background: "linear-gradient(135deg, oklch(23% 0.012 138), oklch(13% 0.008 138))",
    boxShadow: "0 32px 64px rgba(18, 32, 22, 0.26), 0 9px 18px rgba(18, 32, 22, 0.16), inset 0 0 0 1px rgba(255, 255, 255, 0.1)",
    transform: `translate3d(${camera.panX}px, ${camera.panY}px, 0) scale(${camera.scale})`,
    transformOrigin: "center center",
  };
}

function phoneScreen(): CSSProperties {
  return {
    position: "relative",
    width: 392,
    height: 820,
    overflow: "hidden",
    borderRadius: 36,
    background: "#f9fbf7",
  };
}

function desktopFrame(colors: ReturnType<typeof palette>, camera: {scale: number; panX: number; panY: number}): CSSProperties {
  return {
    position: "relative",
    width: 954,
    height: 650,
    padding: "56px 12px 12px",
    borderRadius: 24,
    background: `linear-gradient(180deg, ${colors.surface}, ${colors.line})`,
    boxShadow: "0 24px 56px rgba(18, 32, 22, 0.2), 0 7px 16px rgba(18, 32, 22, 0.14), inset 0 0 0 1px rgba(255, 255, 255, 0.88)",
    transform: `translate3d(${camera.panX}px, ${camera.panY}px, 0) scale(${camera.scale})`,
    transformOrigin: "center center",
  };
}

function desktopScreen(colors: ReturnType<typeof palette>): CSSProperties {
  return {
    width: 930,
    height: 582,
    overflow: "hidden",
    borderRadius: 14,
    background: colors.paper,
    boxShadow: `inset 0 0 0 1px ${colors.line}`,
  };
}

const mediaStyle: CSSProperties = {
  width: "100%",
  height: "100%",
  objectFit: "cover",
  display: "block",
};
