import assert from "node:assert/strict";
import { it } from "vitest";
import { isEven } from "../src/value.js";
it("checks even and odd", () => { assert.equal(isEven(2), true); assert.equal(isEven(3), false); });
