export type DemoDevice = "phone" | "desktop";

export type DemoDesign = {
  name: string;
  register: string;
  visualDirection?: string;
  sourcePath?: string | null;
  colors?: Record<string, string>;
  radii?: Record<string, string>;
  typography?: {
    uiFontFamily?: string;
    displayFontFamily?: string;
    uiStack?: string;
    displayStack?: string;
  };
};

export type DemoScene = {
  id: string;
  title: string;
  copy: string;
  proof?: string;
  startFrame: number;
  durationFrames: number;
  device?: DemoDevice;
  camera?: {
    scale: number;
    panX?: number;
    panY?: number;
  };
};

export type DemoEvent = {
  type: "move" | "click" | "zoom" | "type" | "select";
  t?: number;
  atMs?: number;
  x?: number;
  y?: number;
  scale?: number;
  panX?: number;
  panY?: number;
  durationFrames?: number;
  label?: string;
  value?: string;
  text?: string;
};

export type ProductDemoProps = {
  captureSrc: string;
  posterSrc?: string;
  design: DemoDesign;
  scenes: DemoScene[];
  events: DemoEvent[];
};
