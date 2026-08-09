import { createAudioGraph } from "../src/audio-graph.js";
import {
  createOffscreenRuntime,
  installOffscreenMessageListener,
} from "../src/offscreen-runtime.js";
import { createRemoteClient } from "../src/remote-client.js";

const runtime = createOffscreenRuntime({
  audioGraphFactory(callbacks) {
    return createAudioGraph({
      ...callbacks,
      mediaDevices: navigator.mediaDevices,
      AudioContextClass: AudioContext,
      AudioWorkletNodeClass: AudioWorkletNode,
      workletModuleUrl: chrome.runtime.getURL(
        "offscreen/worklets/liveconv-audio.js",
      ),
    });
  },
  remoteClientFactory: createRemoteClient,
  sendMessage(message) {
    return chrome.runtime.sendMessage(message);
  },
});

installOffscreenMessageListener(runtime, chrome);
