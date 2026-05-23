import { createBuilder } from "vite";

const builder = await createBuilder({}, true);
await builder.buildApp();
