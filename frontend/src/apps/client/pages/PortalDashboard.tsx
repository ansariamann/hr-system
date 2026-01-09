import { useState } from "react";
import { DragDropContext, Droppable, Draggable, type DropResult } from "@hello-pangea/dnd";
import { Card, CardContent } from "../../../shared/components/ui/Card";
import { ApplicationStatus } from "../../../shared/types/enums";
import { cn } from "../../../shared/utils/cn";

// Strict FSM: Only allowed columns for Client
const ALLOWED_COLUMNS = [
    { id: ApplicationStatus.TECHNICAL_REVIEW, title: "To Review" },
    { id: ApplicationStatus.INTERVIEW_SCHEDULED, title: "Interview" },
    { id: ApplicationStatus.OFFER_EXTENDED, title: "Selected" },
    { id: ApplicationStatus.HIRED, title: "Joined" },
];

// Mock Data
const initialApplications = [
    { id: "app-1", candidateName: "Jane Doe", status: ApplicationStatus.TECHNICAL_REVIEW, role: "Senior Engineer" },
    { id: "app-2", candidateName: "John Smith", status: ApplicationStatus.INTERVIEW_SCHEDULED, role: "Product Owner" },
];

export default function PortalDashboard() {
    const [applications, setApplications] = useState(initialApplications);

    const onDragEnd = (result: DropResult) => {
        // Client-side visual update only - Backend would validate FSM
        const { source, destination } = result;

        if (!destination) return;

        if (
            source.droppableId === destination.droppableId &&
            source.index === destination.index
        ) {
            return;
        }

        // Check if transition is valid (Mock FSM)
        // E.g., Review -> Interview is OK. Review -> Hired is NOT.
        // Ideally this logic comes from backend permissions.

        // Update state
        const newApps = [...applications];
        const movedApp = newApps.find(app => app.id === result.draggableId);
        if (movedApp) {
            movedApp.status = destination.droppableId as ApplicationStatus;
            setApplications(newApps);
        }
    };

    const getAppsByStatus = (status: string) => applications.filter(app => app.status === status);

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            <header className="mb-8 flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Candidate Board</h1>
                    <p className="text-gray-500">Manage your assigned candidates</p>
                </div>
                <div className="flex items-center gap-4">
                    <span className="text-sm text-gray-600">Acme Corp</span>
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
                                {(provided, snapshot) => (
                                    <div
                                        {...provided.droppableProps}
                                        ref={provided.innerRef}
                                        className={cn(
                                            "flex-1 flex flex-col gap-3 min-h-[150px] transition-colors rounded-lg",
                                            snapshot.isDraggingOver ? "bg-gray-100" : ""
                                        )}
                                    >
                                        {getAppsByStatus(column.id).map((app, index) => (
                                            <Draggable key={app.id} draggableId={app.id} index={index}>
                                                {(provided, snapshot) => (
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
                                                                <p className="font-semibold text-gray-900">{app.candidateName}</p>
                                                                <p className="text-xs text-gray-500 mt-1">{app.role}</p>
                                                            </CardContent>
                                                        </Card>
                                                    </div>
                                                )}
                                            </Draggable>
                                        ))}
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
