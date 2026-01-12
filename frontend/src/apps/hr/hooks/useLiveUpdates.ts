import { useEffect } from "react";
import { useInvalidate } from "@refinedev/core";

export const useLiveUpdates = () => {
    const invalidate = useInvalidate();

    useEffect(() => {
        // Determine correct endpoint
        const sseUrl = "http://localhost:8000/sse/events";

        // Note: Native EventSource doesn't support headers. 
        // For production, use 'event-source-polyfill' or pass token via query param if backend allows.
        console.log("Connecting to SSE stream at", sseUrl);
        const eventSource = new EventSource(sseUrl);

        eventSource.onopen = () => {
            console.log("SSE Connection Open");
        };

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log("SSE Message:", data);

                // Invalidate resources based on event type
                // Expected format: { event: "candidate_update", payload: { id: 123 } }
                if (data.event === "candidate_update" || data.event === "application_update") {
                    invalidate({
                        resource: "candidates",
                        invalidates: ["list", "detail"],
                    });
                    invalidate({
                        resource: "applications",
                        invalidates: ["list", "detail"],
                    });
                }
            } catch (err) {
                console.error("SSE Parse Error", err);
            }
        };

        eventSource.onerror = (err) => {
            console.error("SSE Error", err);
            eventSource.close();
            // Reconnect logic could go here (EventSource auto-reconnects by default usually)
        };

        return () => {
            eventSource.close();
        };
    }, [invalidate]);
};
