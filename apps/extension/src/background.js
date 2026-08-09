import {
  createBrowserRuntime,
  installBrowserMessageListener,
} from "./browser-runtime.js";

const runtime = createBrowserRuntime({ chromeApi: chrome });
installBrowserMessageListener(runtime, chrome);
