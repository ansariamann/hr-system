import { useState, useEffect } from "react";
import { DragDropContext, Droppable, Draggable, type DropResult } from "@hello-pangea/dnd";
import { Card, CardContent } from "../../../shared/components/ui/Card";
import { ApplicationStatus } from "../../../shared/types/enums";
import { cn } from "../../../shared/utils/cn";
import { apiClient } from "../../../shared/api/client";
import { Loader2, RefreshCw, LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";

// Strict FSM: Only allowed columns for Client
const ALLOWED_COLUMNS = [
    { id: ApplicationStatus.TECHNICAL_REVIEW, title: "To Review" },
    { id: ApplicationStatus.INTERVIEW_SCHEDULED, title: "Interview" },
    { id: ApplicationStatus.OFFER_EXTENDED, title: "Selected" },
    { id: ApplicationStatus.HIRED, title: "Joined" },
];

export default function PortalDashboard() {
    const navigate = useNavigate();
    const [applications, setApplications] = useState<any[]>([]);
    const [clientInfo, setClientInfo] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState("");

    const fetchClientInfo = async () => {
        try {
            const { data } = await apiClient.get("/auth/client");
            setClientInfo(data);
        } catch (err) {
            console.error("Failed to fetch client info", err);
            // If auth fails, redirect to login
            navigate("/portal/auth");
        }
    };

    const fetchApplications = async (isRefresh = false) => {
        try {
            if (isRefresh) setRefreshing(true);
            else setLoading(true);

            const { data } = await apiClient.get("/applications");
            // Check if data is array or paginated
            const apps = Array.isArray(data) ? data : (data.items || []);
            setApplications(apps);
            setError("");
        } catch (err) {
            console.error("Failed to fetch applications", err);
            setError("Failed to load applications. Please try refreshing.");
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchClientInfo();
        fetchApplications();

        // Auto-refresh every 30 seconds
        const interval = setInterval(() => {
            fetchApplications(true);
        }, 30000);

        return () => clearInterval(interval);
    }, []);

    const handleLogout = () => {
        localStorage.removeItem("client_magic_token");
        navigate("/portal/auth");
    };

    const updateApplicationStatus = async (id: string, status: string) => {
        try {
            await apiClient.patch(`/applications/${id}`, { status });
        } catch (err) {
            console.error("Failed to update status", err);
            // Revert changes if needed or show toast
        }
    };

    const onDragEnd = (result: DropResult) => {
        const { source, destination } = result;

        if (!destination) return;

        if (
            source.droppableId === destination.droppableId &&
            source.index === destination.index
        ) {
            return;
        }

        const newStatus = destination.droppableId as ApplicationStatus;
        const appId = result.draggableId;

        // Optimistic Update
        const newApps = applications.map(app =>
            app.id === appId ? { ...app, status: newStatus } : app
        );
        setApplications(newApps);

        // API Call
        updateApplicationStatus(appId, newStatus);
    };

    const getAppsByStatus = (status: string) => applications.filter(app => app.status === status);

    if (loading && !clientInfo) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-gray-50">
                <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
            </div>
        );
    }

    if (error && !applications.length) {
        return (
            <div className="flex min-h-screen items-center justify-center bg-gray-50">
                <div className="text-center">
                    <p className="text-red-600 mb-2">{error}</p>
                    <button onClick={() => fetchApplications()} className="text-blue-600 underline">Try Again</button>
                    <div className="mt-4">
                        <button onClick={handleLogout} className="text-sm text-gray-500 hover:text-gray-700">Logout</button>
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            <header className="mb-8 flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Candidate Board</h1>
                    <p className="text-gray-500">Manage your assigned candidates</p>
                </div>
                <div className="flex items-center gap-4">
                    <div className="text-right hidden sm:block">
                        <p className="text-sm font-medium text-gray-900">{clientInfo?.name || "Loading..."}</p>
                        <p className="text-xs text-gray-500">{clientInfo?.email_domain || ""}</p>
                    </div>
                    <button
                        onClick={() => fetchApplications(true)}
                        className="p-2 text-gray-500 hover:text-blue-600 transition-colors"
                        title="Refresh Data"
                        disabled={refreshing}
                    >
                        <RefreshCw className={cn("h-5 w-5", refreshing ? "animate-spin" : "")} />
                    </button>
                    <button
                        onClick={handleLogout}
                        className="p-2 text-gray-500 hover:text-red-600 transition-colors"
                        title="Logout"
                    >
                        <LogOut className="h-5 w-5" />
                    </button>
                </div>
            </header>

            <DragDropContext onDragEnd={onDragEnd}>
                <div className="flex h-[calc(100vh-12rem)] gap-6 overflow-x-auto pb-4">
                    {ALLOWED_COLUMNS.map((column) => (
                        <div key={column.id} className="flex-shrink-0 w-80 flex flex-col rounded-xl bg-gray-100/50 p-4 border border-gray-200">
                            <h3 className="font-semibold mb-4 flex items-center justify-between text-gray-700">
                                {column.title}
                                <span className="bg-white text-gray-700 shadow-sm rounded-full px-2 py-0.5 text-xs font-medium border">
                                    {getAppsByStatus(column.id).length}
                                </span>
                            </h3>
                            <Droppable droppableId={column.id}>
                                {(provided: any, snapshot: any) => (
                                    <div
                                        {...provided.droppableProps}
                                        ref={provided.innerRef}
                                        className={cn(
                                            "flex-1 flex flex-col gap-3 min-h-[150px] transition-colors rounded-lg",
                                            snapshot.isDraggingOver ? "bg-gray-100" : ""
                                        )}
                                    >
                                        {getAppsByStatus(column.id).length === 0 ? (
                                            <div className="flex flex-col items-center justify-center py-8 text-gray-400 border-2 border-dashed border-gray-200 rounded-lg">
                                                <p className="text-sm">No candidates</p>
                                            </div>
                                        ) : (
                                            getAppsByStatus(column.id).map((app, index) => (
                                                <Draggable key={app.id} draggableId={app.id} index={index}>
                                                    {(provided: any, snapshot: any) => (
                                                        <div
                                                            ref={provided.innerRef}
                                                            {...provided.draggableProps}
                                                            {...provided.dragHandleProps}
                                                            style={{ ...provided.draggableProps.style }}
                                                        >
                                                            <Card className={cn(
                                                                "cursor-grab active:cursor-grabbing hover:shadow-md transition-all border-l-4",
                                                                snapshot.isDragging ? "shadow-lg scale-105 rotate-1" : "",
                                                                "border-l-blue-500" // Dynamic color based on status
                                                            )}>
                                                                <CardContent className="p-4">
                                                                    <p className="font-semibold text-gray-900">
                                                                        {app.candidate?.name || "Unknown Candidate"}
                                                                    </p>
                                                                    <p className="text-xs text-gray-500 mt-1">
                                                                        {app.job_title || app.candidate?.email || "No Role Specified"}
                                                                    </p>
                                                                </CardContent>
                                                            </Card>
                                                        </div>
                                                    )}
                                                </Draggable>
                                            ))
                                        )}
                                        {provided.placeholder}
                                    </div>
                                )}
                            </Droppable>
                        </div>
                    ))}
                </div>
            </DragDropContext>
        </div>
    );
}
