import { Router } from "express";
import { channelLeaderboard } from "../lib/insights.js";

export const channelsRouter = Router();

channelsRouter.get("/channels", (_req, res) => {
  res.json(channelLeaderboard());
});
