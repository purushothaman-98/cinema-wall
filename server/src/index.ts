import path from "node:path";
import { existsSync } from "node:fs";
import express from "express";
import cors from "cors";
import compression from "compression";
import { REPO_ROOT } from "./lib/paths.js";
import { overviewRouter } from "./routes/overview.js";
import { filmsRouter } from "./routes/films.js";
import { channelsRouter } from "./routes/channels.js";

const app = express();
const PORT = Number(process.env.PORT ?? 4000);

app.use(cors());
app.use(compression());

const api = express.Router();
api.use(overviewRouter);
api.use(filmsRouter);
api.use(channelsRouter);
app.use("/api", api);

// If the frontend has been built, serve it from the same process so a
// single `npm start` here is a complete deployable app.
const webDist = path.join(REPO_ROOT, "web", "dist");
if (existsSync(webDist)) {
  app.use(express.static(webDist));
  app.get(/^(?!\/api).*/, (_req, res) => {
    res.sendFile(path.join(webDist, "index.html"));
  });
}

app.listen(PORT, () => {
  console.log(`cinema-wall API listening on :${PORT}`);
});
