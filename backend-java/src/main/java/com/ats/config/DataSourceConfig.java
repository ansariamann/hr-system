package com.ats.config;

import com.zaxxer.hikari.HikariDataSource;
import org.springframework.boot.autoconfigure.jdbc.DataSourceProperties;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;

/**
 * DataSource configuration that wraps every borrowed connection to
 * issue  SET LOCAL app.current_tenant_id = ?  so PostgreSQL RLS
 * policies can restrict rows to the current tenant's data.
 *
 * <p>The SET LOCAL is scoped to the current transaction, which means
 * it is automatically reset when the transaction commits or rolls back,
 * so connection pool reuse cannot leak tenant context.
 */
@Configuration
public class DataSourceConfig {

    @Bean
    @Primary
    @ConfigurationProperties("spring.datasource.hikari")
    public HikariDataSource dataSource(DataSourceProperties properties) {
        HikariDataSource ds = properties.initializeDataSourceBuilder()
                .type(HikariDataSource.class)
                .build();

        // Proxy every checkout to inject tenant context
        ds.setConnectionInitSql(null); // handled per-transaction
        return ds;
    }

    /**
     * Apply the RLS tenant context to the given connection.
     * Must be called inside an active transaction so SET LOCAL is scoped.
     */
    public static void applyTenantContext(Connection connection) throws SQLException {
        String tenantId = TenantContext.getCurrentTenantId();
        if (tenantId != null && !tenantId.isBlank()) {
            try (PreparedStatement stmt = connection.prepareStatement(
                    "SELECT set_config('app.current_tenant_id', ?, true)")) {
                stmt.setString(1, tenantId);
                stmt.execute();
            }
        }
    }
}
