import assert from "node:assert/strict";
import test from "node:test";

import { ApiError } from "./api";
import { mapApiError, sanitizeJobErrorText } from "./errors";

test("maps pydantic 422 detail array to field-level messages without JSON", () => {
  const err = new ApiError(422, "Unprocessable Entity", [
    {
      type: "string_too_short",
      loc: ["body", "email"],
      msg: "String should have at least 3 characters",
      ctx: { min_length: 3 },
    },
    {
      type: "string_too_short",
      loc: ["body", "password"],
      msg: "String should have at least 8 characters",
      ctx: { min_length: 8 },
    },
  ]);
  const mapped = mapApiError(err);
  assert.equal(mapped.fields?.email, "Email must be at least 3 characters.");
  assert.equal(mapped.fields?.password, "Password must be at least 8 characters.");
  assert.ok(!mapped.message.includes("[{"));
});

test("maps string detail and scrubs internal paths or env vars", () => {
  const err = new ApiError(402, "Upgrade required", "Your Free plan includes 1 video per month.");
  const mapped = mapApiError(err);
  assert.equal(mapped.title, "Plan limit reached");
  assert.equal(mapped.message, "Your Free plan includes 1 video per month.");

  const envErr = new ApiError(400, "Missing SNIPZO_STRIPE_SECRET_KEY in /tmp/foo");
  envErr.detail = "Missing SNIPZO_STRIPE_SECRET_KEY in /tmp/foo";
  const cleaned = mapApiError(envErr);
  assert.ok(!cleaned.message.includes("SNIPZO_"));
  assert.ok(!cleaned.message.includes("/tmp/"));
});

test("maps network failure and 5xx cleanly", () => {
  const net = mapApiError(new TypeError("Failed to fetch"));
  assert.equal(net.isNetwork, true);
  assert.equal(net.title, "Service unavailable");

  const status0 = mapApiError(new ApiError(0, "Service unavailable"));
  assert.equal(status0.isNetwork, true);

  const server500 = mapApiError(new ApiError(500, "Internal Server Error", "Traceback..."));
  assert.equal(server500.title, "Service error");
  assert.ok(!server500.message.includes("Traceback"));
});

test("sanitizes raw job failure text", () => {
  const ffprobe = sanitizeJobErrorText(
    "ffprobe could not read /tmp/snipzo-src-1/a.mp4: moov atom not found",
  );
  assert.ok(!ffprobe.includes("/tmp"));
  assert.ok(!ffprobe.includes("ffprobe"));
  assert.ok(ffprobe.includes("valid MP4"));

  const noSpeech = sanitizeJobErrorText("Transcription produced no text for project 2a3d490d75bd.");
  assert.ok(!noSpeech.includes("2a3d490d75bd"));
});
