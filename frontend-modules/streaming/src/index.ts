import { defineModule, defineModuleRoute } from "@ocelescope/core";
import { SparklesIcon } from "lucide-react";
import Hello from "./routes/Hello";

const helloRoute = defineModuleRoute({
  name: "hello",
  label: "Hello",
  component: Hello,
});

export default defineModule({
  name: "streaming",
  label: "Streaming",
  description: "Object-centric process discovery on event streams with bounded buffers and eviction heuristics",
  authors: [{ name: "Menne, Sebastian" }],
  icon: SparklesIcon,
  routes: [helloRoute],
});
