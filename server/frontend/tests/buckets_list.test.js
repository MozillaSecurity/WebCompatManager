import { afterEach, expect, test, vi } from "vitest";
import { nextTick } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import { render, fireEvent } from "@testing-library/vue";
import List from "../src/components/Buckets/List.vue";
import { listBuckets } from "../src/api.js";
import { emptyBuckets, buckets } from "./fixtures.js";

// This line will mock all calls to functions in ../src/api.js
vi.mock("../src/api.js");
// Mocking calls to lodash._throttle during tests
vi.mock("lodash/throttle", () => ({ default: vi.fn((fn) => fn) }));

afterEach(() => vi.resetAllMocks());

const defaultQueryStr = `{
  "op": "AND",
  "bug__isnull": true,
  "triage_status__isnull": true
}`;

test("bucket list has no buckets", async () => {
  const router = createRouter({
    history: createWebHistory(),
    routes: [],
  });
  listBuckets.mockResolvedValue(emptyBuckets);
  await render(List, {
    global: {
      plugins: [router],
    },
    props: {
      canEdit: true,
      providers: [],
      watchUrl: "",
      activityRange: 14,
    },
  });
  await nextTick();

  expect(listBuckets).toHaveBeenCalledTimes(1);
  expect(listBuckets).toHaveBeenCalledWith({
    vue: "1",
    limit: 100,
    offset: "0",
    ordering: "-priority_score,-size,-latest_report",
    query: defaultQueryStr,
  });

  await nextTick();
  // Assert no bucket is displayed in the table
  expect(document.querySelector("tbody tr")).toBeNull();
});

test("bucket list has two buckets", async () => {
  const router = createRouter({
    history: createWebHistory(),
    routes: [],
  });
  listBuckets.mockResolvedValue(buckets);
  const { getByText } = await render(List, {
    global: {
      plugins: [router],
    },
    props: {
      canEdit: true,
      providers: [],
      watchUrl: "",
      activityRange: 14,
    },
  });
  await nextTick();

  expect(listBuckets).toHaveBeenCalledTimes(1);
  expect(listBuckets).toHaveBeenCalledWith({
    vue: "1",
    limit: 100,
    offset: "0",
    ordering: "-priority_score,-size,-latest_report",
    query: defaultQueryStr,
  });

  await nextTick();
  // Assert two buckets (one assigned to a bug, the other not) are displayed in the table
  expect(document.querySelectorAll("tbody tr").length).toBe(2);
  getByText("A short description for bucket 1");
  getByText("A short description for bucket 2");
});

const renderList = async () => {
  const router = createRouter({ history: createWebHistory(), routes: [] });
  listBuckets.mockResolvedValue(emptyBuckets);
  const utils = await render(List, {
    global: { plugins: [router] },
    props: {
      canEdit: true,
      providers: [],
      countries: [{ code: "GB", name: "United Kingdom" }],
      watchUrl: "",
      activityRange: 14,
    },
  });
  await nextTick();
  return utils;
};

test("typing alone does not refetch; Enter submits a complete term", async () => {
  const { getByTestId } = await renderList();
  listBuckets.mockClear();
  const input = getByTestId("query-input");
  // Typing updates the field locally but must NOT trigger a fetch.
  await fireEvent.update(input, "domain:youtube.com");
  await fireEvent.input(input);
  await nextTick();
  expect(listBuckets).not.toHaveBeenCalled();
  // The term is complete, so Enter submits directly — no Escape needed.
  await fireEvent.keyDown(input, { key: "Enter" });
  await nextTick();
  await nextTick();
  expect(listBuckets).toHaveBeenCalled();
  const call = listBuckets.mock.calls.at(-1)[0];
  const query = JSON.parse(call.query);
  expect(query[1]).toEqual({
    op: "OR",
    domain: "youtube.com",
    domain__endswith: ".youtube.com",
  });
});

test("invalid query (unbalanced paren) blocks the fetch on Enter", async () => {
  const { getByTestId, queryByTestId } = await renderList();
  listBuckets.mockClear();
  const input = getByTestId("query-input");
  await fireEvent.update(input, "(domain:a");
  await fireEvent.input(input);
  await nextTick();
  await fireEvent.keyDown(input, { key: "Enter" });
  await nextTick();
  await nextTick();
  expect(queryByTestId("query-error")).not.toBeNull();
  expect(listBuckets).not.toHaveBeenCalled();
});
