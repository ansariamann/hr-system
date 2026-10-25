package com.ats.config;

/**
 * Thread-local holder for the current authenticated tenant (client) ID.
 * Set by the JWT filter on every request and cleared on response.
 * Used by the HikariCP connection interceptor to issue
 *   SET LOCAL app.current_tenant_id = '<uuid>'
 * so PostgreSQL RLS policies enforce tenant isolation.
 */
public final class TenantContext {

    private static final ThreadLocal<String> CURRENT_TENANT = new ThreadLocal<>();

    private TenantContext() {}

    public static void setCurrentTenantId(String tenantId) {
        CURRENT_TENANT.set(tenantId);
    }

    public static String getCurrentTenantId() {
        return CURRENT_TENANT.get();
    }

    public static void clear() {
        CURRENT_TENANT.remove();
    }
}
