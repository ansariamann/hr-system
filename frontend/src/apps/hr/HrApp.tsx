import { Refine } from "@refinedev/core";
import { ThemedLayoutV2, ErrorComponent, RefineThemes, useNotificationProvider } from "@refinedev/antd";
import "@refinedev/antd/dist/reset.css";
import { ConfigProvider, App as AntdApp } from "antd";
import routerBindings, { NavigateToResource, UnsavedChangesNotifier, DocumentTitleHandler } from "@refinedev/react-router-v6";
import { BrowserRouter, Routes, Route, Outlet } from "react-router-dom";
import simpleRestDataProvider from "@refinedev/simple-rest";

import { apiClient } from "../../../shared/api/client";

// Pages
import { CandidateList } from "./pages/candidates/list";
import { CandidateShow } from "./pages/candidates/show";
// import { CandidateEdit } from "./pages/candidates/edit";
import { ApplicationList } from "./pages/applications/list";
import { HrCopilot } from "./components/HrCopilot";

const API_URL = "http://localhost:8000";

import { useLiveUpdates } from "./hooks/useLiveUpdates";
import { authProvider } from "./authProvider";
import PortalLogin from "../client/pages/PortalLogin";

export default function HrApp() {
    useLiveUpdates();

    return (
        <ConfigProvider theme={{ token: { colorPrimary: '#1677ff' } }}>
            <AntdApp>
                <Refine
                    dataProvider={simpleRestDataProvider(API_URL, apiClient)}
                    notificationProvider={useNotificationProvider}
                    authProvider={authProvider}
                    routerProvider={routerBindings}
                    LoginPage={() => <PortalLogin />}
                    resources={[
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
                            <Route index element={<NavigateToResource resource="candidates" />} />

                            <Route path="candidates">
                                <Route index element={<CandidateList />} />
                                <Route path=":id" element={<CandidateShow />} />
                            </Route>

                            <Route path="applications">
                                <Route index element={<ApplicationList />} />
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
