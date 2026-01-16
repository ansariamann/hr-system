import { Refine } from "@refinedev/core";
import { ThemedLayoutV2, ErrorComponent, useNotificationProvider } from "@refinedev/antd";
import "@refinedev/antd/dist/reset.css";
import { ConfigProvider, App as AntdApp } from "antd";
import routerBindings, { UnsavedChangesNotifier, DocumentTitleHandler } from "@refinedev/react-router-v6";
import { Routes, Route, Outlet } from "react-router-dom";
import simpleRestDataProvider from "@refinedev/simple-rest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { apiClient } from "../../shared/api/client";

// Pages
import { CandidateList } from "./pages/candidates/list";
import { CandidateShow } from "./pages/candidates/show";
// import { CandidateEdit } from "./pages/candidates/edit";
import { ApplicationList } from "./pages/applications/list";
import { MasterDatabaseList } from "./pages/master/list";
import { HrCopilot } from "./components/HrCopilot";
import { DashboardOverview } from "./pages/dashboard/overview";
import { JobList } from "./pages/jobs/list";

const API_URL = "http://localhost:8000";

import { useLiveUpdates } from "./hooks/useLiveUpdates";
import { authProvider } from "./authProvider";

const queryClient = new QueryClient();

function HrAppContent() {
    useLiveUpdates();

    return (
        <ConfigProvider theme={{ token: { colorPrimary: '#1677ff' } }}>
            <AntdApp>
                <Refine
                    dataProvider={simpleRestDataProvider(API_URL, apiClient as any)}
                    notificationProvider={useNotificationProvider}
                    authProvider={authProvider}
                    routerProvider={routerBindings}
                    resources={[
                        {
                            name: "dashboard",
                            list: "/admin",
                            meta: { label: "Dashboard" }
                        },
                        {
                            name: "master",
                            list: "/admin/master",
                            meta: { label: "Master Database" }
                        },
                        {
                            name: "jobs",
                            list: "/admin/jobs",
                            meta: { label: "Jobs" }
                        },
                        {
                            name: "candidates",
                            list: "/admin/candidates",
                            show: "/admin/candidates/:id",
                            // edit: "/admin/candidates/:id/edit",
                            meta: {
                                label: "Candidates",
                            },
                        },
                        {
                            name: "applications",
                            list: "/admin/applications",
                            meta: { label: "Applications" }
                        }
                    ]}
                    options={{
                        syncWithLocation: true,
                        warnWhenUnsavedChanges: true,
                    }}
                >
                    <Routes>
                        <Route
                            element={
                                <ThemedLayoutV2>
                                    <Outlet />
                                    <HrCopilot />
                                </ThemedLayoutV2>
                            }
                        >
                            <Route index element={<DashboardOverview />} />

                            <Route path="master">
                                <Route index element={<MasterDatabaseList />} />
                            </Route>

                            <Route path="candidates">
                                <Route index element={<CandidateList />} />
                                <Route path=":id" element={<CandidateShow />} />
                            </Route>

                            <Route path="applications">
                                <Route index element={<ApplicationList />} />
                            </Route>

                            <Route path="jobs">
                                <Route index element={<JobList />} />
                            </Route>

                            <Route path="*" element={<ErrorComponent />} />
                        </Route>
                    </Routes>
                    <UnsavedChangesNotifier />
                    <DocumentTitleHandler />
                </Refine>
            </AntdApp>
        </ConfigProvider >
    );
}

export default function HrApp() {
    return (
        <QueryClientProvider client={queryClient}>
            <HrAppContent />
        </QueryClientProvider>
    );
}
