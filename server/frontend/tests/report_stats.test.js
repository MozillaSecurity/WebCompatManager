import { nextTick } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import { render } from "@testing-library/vue";
import { mount } from "@vue/test-utils";
import Stats from "../src/components/ReportStats.vue";
import { reportStats, listBuckets } from "../src/api.js";
import { emptyReportStats, reportStatsData, buckets } from "./fixtures.js";
import "lodash/throttle";

// This line will mock all calls to functions in ../src/api.js
jest.mock("../src/api.js");
// Mocking calls to lodash._throttle during tests
jest.mock("lodash/throttle", () => jest.fn((fn) => fn));

afterEach(jest.resetAllMocks);

test("empty stats doesn't break", async () => {
  const router = createRouter({
    history: createWebHistory(),
    routes: [],
  });

  reportStats.mockResolvedValue(emptyReportStats);
  await render(Stats, {
    global: {
      plugins: [router],
    },
    props: {
      providers: [],
      canEdit: true,
      activityRange: 14,
    },
  });
  await nextTick();

  expect(reportStats).toHaveBeenCalledTimes(1);
  expect(reportStats).toHaveBeenCalledWith();
  expect(listBuckets).toHaveBeenCalledTimes(0);

  await nextTick();
  // Assert no signature is displayed in the table
  expect(document.querySelector("tbody tr")).toBeNull();
});

test("stats are shown", async () => {
  const router = createRouter({
    history: createWebHistory(),
    routes: [],
  });

  reportStats.mockResolvedValue(reportStatsData);
  listBuckets.mockResolvedValue(buckets);
  const { getByText } = await render(Stats, {
    global: {
      plugins: [router],
    },
    props: {
      providers: [],
      canEdit: true,
      activityRange: 14,
    },
  });
  await nextTick();

  expect(reportStats).toHaveBeenCalledTimes(1);
  expect(reportStats).toHaveBeenCalledWith();
  expect(listBuckets).toHaveBeenCalledTimes(1);
  await nextTick();
  await nextTick();
  await nextTick();

  // Assert two buckets are displayed in the table
  expect(document.querySelectorAll("tbody tr").length).toBe(2);
  getByText("A short description for bucket 1");
  const buttonLink = getByText("1630739");
  expect(buttonLink).toHaveProperty("href", buckets.results[0].bug_urltemplate);
  expect(buttonLink).toHaveProperty("target", "_blank");
  getByText("A short description for bucket 2");
  getByText("Assign an existing bug");
});

test("stats use hash params", async () => {
  reportStats.mockResolvedValue(reportStatsData);
  listBuckets.mockResolvedValue(buckets);
  const router = createRouter({
    history: createWebHistory(),
    routes: [],
  });
  // Set initial route with hash
  router.push({ path: "/stats", hash: "#sort=id&alltools=1" });
  await render(Stats, {
    global: {
      plugins: [router],
    },
    props: {
      providers: [],
      canEdit: true,
      createBucketUrl: "",
      activityRange: 14,
    },
  });
  await nextTick();

  expect(reportStats).toHaveBeenCalledTimes(1);
  expect(reportStats).toHaveBeenCalledWith();
  expect(listBuckets).toHaveBeenCalledTimes(1);
  await nextTick();
  await nextTick();
  await nextTick();

  expect(document.querySelectorAll("tbody tr").length).toBe(2);
});

test("stats are sortable", async () => {
  reportStats.mockResolvedValue(reportStatsData);
  listBuckets.mockResolvedValue(buckets);

  const route = {
    hash: "",
  };

  // Create a mock router with push method
  const router = {
    push: jest.fn((value) => {
      const newHash = value.hash.slice(1);
      const currentHash = route.hash.slice(1);

      // Get the new sort parameter (e.g., "id" or "-id")
      const newSortParam = newHash.split("=")[1];
      const newSortKey = newSortParam.replace(/^-/, "");

      const currentParams = currentHash ? currentHash.split(",") : [];

      const otherParams = currentParams
        .filter((param) => {
          if (!param.startsWith("sort=")) return true;
          const existingSortKey = param.split("=")[1].replace(/^-/, "");
          return existingSortKey !== newSortKey;
        })
        .map((param) => {
          if (param.startsWith("sort=")) {
            return param.slice(5);
          }
          return param;
        });

      // Combine the new sort with existing parameters
      route.hash = "#" + [newHash, ...otherParams].filter(Boolean).join(",");
    }),
  };

  const wrapper = mount(Stats, {
    props: {
      restricted: false,
      providers: [],
      activityRange: 14,
    },
    global: {
      stubs: {
        RouterLink: true,
      },
      mocks: {
        $route: route,
        $router: router,
      },
    },
  });

  await nextTick();

  expect(reportStats).toHaveBeenCalledTimes(1);
  expect(listBuckets).toHaveBeenCalledTimes(1);
  await nextTick();
  await nextTick();
  await nextTick();

  let rows = wrapper.findAll("tbody tr");
  expect(rows.length).toBe(2);
  // sorted by daily count by default
  expect(rows[0].find("td").text()).toBe("2");
  expect(rows[1].find("td").text()).toBe("1");
  expect(route.hash).toBe("");

  await wrapper.find("thead tr th").trigger("click");
  await nextTick();

  rows = wrapper.findAll("tbody tr");
  expect(rows.length).toBe(2);
  // sorted by id now
  expect(rows[0].find("td").text()).toBe("2");
  expect(rows[1].find("td").text()).toBe("1");
  expect(router.push).toHaveBeenCalledTimes(1);
  expect(route.hash).toBe("#sort=-id");

  await wrapper.find("thead th").trigger("click");
  await nextTick();

  rows = wrapper.findAll("tbody tr");
  expect(rows.length).toBe(2);
  // sorted by -id now
  expect(rows[0].find("td").text()).toBe("1");
  expect(rows[1].find("td").text()).toBe("2");
  expect(route.hash).toBe("#sort=id");

  await wrapper.find("thead th + th").trigger("click", { key: "Control" });

  await nextTick();

  expect(route.hash).toBe("#sort=-description,id");
});
