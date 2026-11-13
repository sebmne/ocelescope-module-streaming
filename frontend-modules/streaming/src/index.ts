import { defineModule, defineModuleRoute } from "@ocelescope/core";
import { WavesIcon } from "lucide-react";
import StreamingPage from "./StreamingPage";

export default defineModule({
  name: "streaming",
  label: "Streaming",
  description: "Object-centric process discovery on event streams with bounded buffers and eviction heuristics",
  authors: [{ name: "Menne, Sebastian" }],
  icon: WavesIcon,
  routes: [defineModuleRoute({ name: "runs", label: "Streaming", requiresOcel: true, component: StreamingPage })],
});
