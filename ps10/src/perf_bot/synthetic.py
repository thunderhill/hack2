"""Synthetic data generator for the Performance Bottleneck Explanation Bot.

Generates a realistic DB connection pool exhaustion + GC pressure cascade scenario.
"""

from .models import MetricsInput


def generate_synthetic_data() -> MetricsInput:
    """Return a MetricsInput with a realistic bottleneck scenario.

    Scenario: Java microservice under load with DB pool exhaustion causing
    thread starvation, which triggers GC pressure from queued request objects,
    leading to cascading latency increases.
    """
    error_logs = """\
2026-03-20 14:23:01.412 WARN  [http-nio-8080-exec-47] c.e.db.ConnectionPool - Timeout waiting for connection from pool (waited 30001ms)
2026-03-20 14:23:01.413 ERROR [http-nio-8080-exec-47] c.e.api.UserController - HikariPool-1 - Connection is not available, request timed out after 30000ms
2026-03-20 14:23:02.001 WARN  [http-nio-8080-exec-12] c.e.db.ConnectionPool - Timeout waiting for connection from pool (waited 30001ms)
2026-03-20 14:23:02.345 ERROR [http-nio-8080-exec-12] c.e.api.OrderController - HikariPool-1 - Connection is not available, request timed out after 30000ms
2026-03-20 14:23:03.110 WARN  [GC overhead] java.lang.OutOfMemoryError: GC overhead limit exceeded
2026-03-20 14:23:03.115 ERROR [http-nio-8080-exec-3]  c.e.api.ProductController - java.lang.OutOfMemoryError: GC overhead limit exceeded
2026-03-20 14:23:04.200 WARN  [http-nio-8080-exec-8]  c.e.service.OrderService - Slow query detected: SELECT * FROM orders WHERE user_id=? took 4821ms
2026-03-20 14:23:05.001 ERROR [http-nio-8080-exec-22] c.e.api.CartController - java.util.concurrent.RejectedExecutionException: Thread pool queue full (size=200)
2026-03-20 14:23:05.450 WARN  [http-nio-8080-exec-31] c.e.cache.CacheManager - Cache miss rate 94% — cache may be thrashing
2026-03-20 14:23:06.003 ERROR [scheduler-1] c.e.monitor.HealthCheck - Health check FAILED: DB ping took 8234ms (threshold: 1000ms)
"""

    trace_data = """\
TraceID: abc123def456  Span: GET /api/orders/user/{id}  Duration: 12450ms
  ├─ Span: AuthService.validateToken          Duration: 45ms     OK
  ├─ Span: HikariPool.getConnection           Duration: 9821ms   SLOW (pool wait)
  │   └─ Span: JDBC.executeQuery (orders)     Duration: 4821ms   SLOW
  │       └─ SQL: SELECT * FROM orders WHERE user_id=? AND status IN (?,?,?)
  ├─ Span: ProductService.enrichItems         Duration: 1234ms
  │   └─ Span: HikariPool.getConnection       Duration: 987ms    pool contention
  └─ Span: ResponseSerializer.toJSON          Duration: 523ms

TraceID: xyz789abc012  Span: POST /api/cart/checkout  Duration: 18230ms
  ├─ Span: AuthService.validateToken          Duration: 51ms     OK
  ├─ Span: HikariPool.getConnection           Duration: 14200ms  CRITICAL (pool exhausted)
  └─ Span: TIMEOUT                            Duration: 18230ms  RejectedExecutionException

TraceID: pqr456stu789  Span: GET /api/products/search  Duration: 6100ms
  ├─ Span: CacheLayer.get                     Duration: 2ms      MISS
  ├─ Span: HikariPool.getConnection           Duration: 3800ms   SLOW
  └─ Span: ElasticSearchClient.query          Duration: 2100ms
"""

    return MetricsInput(
        app_name="OrderService",
        environment="prod",
        app_type="Java",
        # CPU metrics — elevated due to GC overhead + thread contention
        cpu_current_pct=87.3,
        cpu_avg_1h_pct=79.1,
        cpu_peak_pct=96.2,
        # Memory metrics — GC pressure scenario
        memory_used_mb=7680,
        memory_total_mb=8192,
        gc_pause_count=142,
        gc_pause_avg_ms=380.5,
        # Response times — cascading latency
        response_avg_ms=4200.0,
        response_p95_ms=11800.0,
        response_p99_ms=18500.0,
        slowest_endpoint="POST /api/cart/checkout",
        # Logs and traces
        error_logs=error_logs,
        trace_data=trace_data,
        # Config — undersized pool is the root cause
        thread_pool_size=200,
        db_pool_size=10,
        cache_enabled=False,
        timeout_ms=30000,
    )
