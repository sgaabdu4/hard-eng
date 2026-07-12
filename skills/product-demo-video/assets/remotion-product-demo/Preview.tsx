import React, {useMemo} from "react";
import {Player} from "@remotion/player";
import {ProductDemo} from "./ProductDemo";
import {demoDesign} from "./design.generated";
import {sampleEvents, sampleScenes} from "./story.sample";

export function DemoPreview() {
  const inputProps = useMemo(
    () => ({
      captureSrc: "capture/product-demo.webm",
      design: demoDesign,
      scenes: sampleScenes,
      events: sampleEvents,
    }),
    [],
  );

  return (
    <Player
      component={ProductDemo}
      durationInFrames={1800}
      compositionWidth={1440}
      compositionHeight={900}
      fps={30}
      inputProps={inputProps}
      controls
      style={{width: "100%", maxWidth: 1440}}
    />
  );
}
