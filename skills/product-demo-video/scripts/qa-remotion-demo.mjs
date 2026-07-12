#!/usr/bin/env node
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

function parseArgs(argv) {
  const args = {
    video: argv[0],
    events: undefined,
    out: ".demo-video-qa",
    samples: undefined,
    minZoom: 1.28,
    minStddev: 8,
  };

  for (let index = 1; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--events") args.events = argv[++index];
    else if (arg === "--out") args.out = argv[++index];
    else if (arg === "--samples") args.samples = argv[++index];
    else if (arg === "--min-zoom") args.minZoom = Number(argv[++index]);
    else if (arg === "--min-stddev") args.minStddev = Number(argv[++index]);
    else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (!args.video) {
    printHelp();
    process.exit(1);
  }

  return {
    ...args,
    video: resolve(args.video),
    events: args.events ? resolve(args.events) : undefined,
    out: resolve(args.out),
  };
}

function printHelp() {
  console.log(`Usage:
  node <skill>/scripts/qa-remotion-demo.mjs <video.mp4> [--events product-demo-events.json] [--samples 3,10,18] [--out .demo-video-qa] [--min-zoom 1.28]

Checks video metadata, nonblank sampled frames, zoom event scale, and cursor
visibility near recorded cursor coordinates. It also writes PNG review frames.`);
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    encoding: options.encoding ?? "utf8",
    maxBuffer: options.maxBuffer ?? 30 * 1024 * 1024,
  });

  if (result.status !== 0) {
    throw new Error(`${command} failed: ${result.stderr || result.stdout}`);
  }

  return result.stdout;
}

function ffprobe(video) {
  const raw = run("ffprobe", [
    "-v",
    "error",
    "-show_entries",
    "format=duration,size",
    "-show_entries",
    "stream=codec_name,width,height,r_frame_rate",
    "-of",
    "json",
    video,
  ]);
  const metadata = JSON.parse(raw);
  const stream = metadata.streams?.[0] ?? {};
  const format = metadata.format ?? {};
  return {
    codec: stream.codec_name,
    width: Number(stream.width),
    height: Number(stream.height),
    frameRate: stream.r_frame_rate,
    duration: Number(format.duration),
    size: Number(format.size),
  };
}

function readEvents(path) {
  if (!path) return [];
  if (!existsSync(path)) throw new Error(`Events file not found: ${path}`);
  const parsed = JSON.parse(readFileSync(path, "utf8"));
  if (!Array.isArray(parsed)) throw new Error("Events JSON must be an array.");
  return parsed;
}

function sampleTimes(options, metadata, events) {
  if (options.samples) {
    return options.samples
      .split(",")
      .map((value) => Number(value.trim()))
      .filter((value) => Number.isFinite(value) && value >= 0);
  }

  const base = [
    0.5,
    metadata.duration * 0.25,
    metadata.duration * 0.5,
    metadata.duration * 0.75,
    Math.max(0, metadata.duration - 0.8),
  ];
  const eventTimes = events
    .filter((event) => event.type === "click" || event.type === "zoom")
    .slice(0, 8)
    .map((event) => Number(event.t ?? event.atMs ?? 0) / 1000)
    .filter((value) => value > 0);

  return [...new Set([...base, ...eventTimes].map((value) => Number(value.toFixed(2))))].sort(
    (a, b) => a - b,
  );
}

function extractPng(video, second, outDir) {
  const outPath = join(outDir, `frame-${second.toFixed(2).replace(".", "_")}s.png`);
  run("ffmpeg", [
    "-hide_banner",
    "-loglevel",
    "error",
    "-ss",
    String(second),
    "-i",
    video,
    "-frames:v",
    "1",
    outPath,
  ]);
  return outPath;
}

function rawFrame(video, second, width = 320, height = 180) {
  const result = spawnSync(
    "ffmpeg",
    [
      "-hide_banner",
      "-loglevel",
      "error",
      "-ss",
      String(second),
      "-i",
      video,
      "-frames:v",
      "1",
      "-vf",
      `scale=${width}:${height}:force_original_aspect_ratio=decrease,pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2`,
      "-f",
      "rawvideo",
      "-pix_fmt",
      "rgb24",
      "-",
    ],
    { encoding: "buffer", maxBuffer: width * height * 3 + 1024 },
  );

  if (result.status !== 0) {
    throw new Error(`ffmpeg raw frame failed: ${result.stderr.toString("utf8")}`);
  }

  return result.stdout;
}

function analyzeFrame(buffer) {
  let sum = 0;
  let sumSq = 0;
  let dark = 0;
  const pixels = buffer.length / 3;

  for (let index = 0; index < buffer.length; index += 3) {
    const luma = 0.2126 * buffer[index] + 0.7152 * buffer[index + 1] + 0.0722 * buffer[index + 2];
    sum += luma;
    sumSq += luma * luma;
    if (luma < 42) dark += 1;
  }

  const mean = sum / pixels;
  const variance = Math.max(0, sumSq / pixels - mean * mean);
  return {
    mean: Number(mean.toFixed(2)),
    stddev: Number(Math.sqrt(variance).toFixed(2)),
    darkPixelRatio: Number((dark / pixels).toFixed(4)),
  };
}

function cursorVisibilityChecks(video, metadata, events) {
  const candidates = events
    .filter((event) => (event.type === "click" || event.type === "move") && event.x && event.y)
    .slice(0, 12);

  return candidates.map((event) => {
    const t = Number(event.t ?? event.atMs ?? 0) / 1000;
    const crop = 64;
    const x = Math.max(0, Math.round(Number(event.x) - crop / 2));
    const y = Math.max(0, Math.round(Number(event.y) - crop / 2));
    const result = spawnSync(
      "ffmpeg",
      [
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        String(t),
        "-i",
        video,
        "-frames:v",
        "1",
        "-vf",
        `crop=${crop}:${crop}:${Math.min(x, metadata.width - crop)}:${Math.min(y, metadata.height - crop)}`,
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-",
      ],
      { encoding: "buffer", maxBuffer: crop * crop * 3 + 1024 },
    );

    if (result.status !== 0) {
      return {
        t,
        x: event.x,
        y: event.y,
        passed: false,
        reason: result.stderr.toString("utf8"),
      };
    }

    const analysis = analyzeFrame(result.stdout);
    return {
      t,
      x: event.x,
      y: event.y,
      darkPixelRatio: analysis.darkPixelRatio,
      passed: analysis.darkPixelRatio >= 0.01,
    };
  });
}

function zoomChecks(events, minZoom) {
  return events
    .filter((event) => event.type === "zoom")
    .map((event) => ({
      t: Number(event.t ?? event.atMs ?? 0),
      scale: Number(event.scale ?? 1),
      passed: Number(event.scale ?? 1) >= minZoom,
    }));
}

function main() {
  const options = parseArgs(process.argv.slice(2));
  if (!existsSync(options.video)) throw new Error(`Video not found: ${options.video}`);
  mkdirSync(options.out, { recursive: true });

  const metadata = ffprobe(options.video);
  const events = readEvents(options.events);
  const times = sampleTimes(options, metadata, events);
  const samples = times.map((second) => {
    const png = extractPng(options.video, second, options.out);
    const analysis = analyzeFrame(rawFrame(options.video, second));
    return {
      second,
      png,
      ...analysis,
      passed: analysis.stddev >= options.minStddev,
    };
  });

  const zoom = zoomChecks(events, options.minZoom);
  const cursor = cursorVisibilityChecks(options.video, metadata, events);
  const report = {
    video: options.video,
    basename: basename(options.video),
    metadata,
    thresholds: {
      minStddev: options.minStddev,
      minZoom: options.minZoom,
    },
    checks: {
      metadata: {
        passed: metadata.width > 0 && metadata.height > 0 && metadata.duration > 0 && metadata.size > 1_000_000,
      },
      samples,
      zoom,
      cursor,
    },
  };

  const reportPath = join(options.out, "visual-qa-report.json");
  writeFileSync(reportPath, JSON.stringify(report, null, 2));

  const failures = [
    !report.checks.metadata.passed && "metadata",
    ...samples.filter((sample) => !sample.passed).map((sample) => `sample:${sample.second}`),
    ...zoom.filter((item) => !item.passed).map((item) => `zoom:${item.t}`),
    ...cursor.filter((item) => !item.passed).map((item) => `cursor:${item.t}`),
  ].filter(Boolean);

  console.log(`report=${reportPath}`);
  console.log(`frames=${options.out}`);
  if (failures.length > 0) {
    console.error(`failed=${failures.join(",")}`);
    process.exit(1);
  }
  console.log("visual_qa=pass");
}

try {
  main();
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
