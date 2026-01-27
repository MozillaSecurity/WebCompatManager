import { createRouter, createWebHistory } from "vue-router";

import ReportsList from "./components/Reports/List.vue";
import BucketsList from "./components/Buckets/List.vue";

const routes = [
  {
    // Be careful to keep this route up-to-date with the one in server/reportmanager/urls.py
    path: "/reportmanager/reports/",
    name: "reports-list",
    component: ReportsList,
  },
  {
    // Be careful to keep this route up-to-date with the one in server/reportmanager/urls.py
    path: "/reportmanager/reports/watch/:bucketid/",
    name: "reports-watch",
    component: ReportsList,
  },
  {
    // Be careful to keep this route up-to-date with the one in server/reportmanager/urls.py
    path: "/reportmanager/buckets/",
    name: "buckets-list",
    component: BucketsList,
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
