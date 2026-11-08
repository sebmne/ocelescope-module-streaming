import type { OcelescopeConfig } from "@ocelescope/core";
import discovery from "@ocelescope/discovery";
import logOverview from "@ocelescope/log-overview";
import management from "@ocelescope/management";

// `pnpm run add:frontend` adds local frontend modules here.
export default {
	modules: [management, logOverview, discovery],
} satisfies OcelescopeConfig;
