import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setJpegQuality(92);
Config.setPixelFormat("yuv420p");
Config.setOverwriteOutput(true);
Config.setChromiumOpenGlRenderer("swangle");
