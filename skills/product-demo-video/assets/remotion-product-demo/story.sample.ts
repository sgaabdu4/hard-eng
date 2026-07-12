import type {DemoEvent, DemoScene} from "./demo-types";

export const sampleScenes: DemoScene[] = [
  {
    id: "opening",
    title: "Today is clear",
    copy: "Show the primary product promise in the first few seconds.",
    proof: "Replace this sample copy with buyer-facing proof from the real workflow.",
    startFrame: 0,
    durationFrames: 180,
    device: "phone",
  },
  {
    id: "action",
    title: "Create the work",
    copy: "Drive the real UI with Playwright, then let Remotion handle the camera.",
    proof: "Zooms should scale the frame, chrome, and product capture together.",
    startFrame: 180,
    durationFrames: 240,
    device: "phone",
  },
  {
    id: "desktop",
    title: "Desktop review",
    copy: "If the story claims a desktop view, show a real desktop frame.",
    proof: "Device claims must be visually true.",
    startFrame: 420,
    durationFrames: 240,
    device: "desktop",
  },
];

export const sampleEvents: DemoEvent[] = [
  {type: "move", t: 900, x: 1130, y: 500},
  {type: "click", t: 1200, x: 1130, y: 500},
  {type: "zoom", t: 1700, x: 1130, y: 500, scale: 1.34, panX: -60, panY: -20},
  {type: "move", t: 6400, x: 1120, y: 730},
  {type: "click", t: 6750, x: 1120, y: 730},
];
