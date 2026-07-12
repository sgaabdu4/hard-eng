import React from "react";
import {Composition} from "remotion";
import {ProductDemo} from "./ProductDemo";
import {demoDesign} from "./design.generated";
import {sampleEvents, sampleScenes} from "./story.sample";

export function RemotionRoot() {
  return (
    <Composition
      id="ProductDemo"
      component={ProductDemo}
      durationInFrames={1800}
      fps={30}
      width={1440}
      height={900}
      defaultProps={{
        captureSrc: "capture/product-demo.webm",
        design: demoDesign,
        scenes: sampleScenes,
        events: sampleEvents,
      }}
    />
  );
}
