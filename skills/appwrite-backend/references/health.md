# Health

Health checks self-hosted Appwrite.

---

## Contents

- Overall Health
- Service Checks
- Queue Monitoring
- Certificate Check
- Time Sync
- Public Cloud Note
- Monitoring Integration
- Horizontal Scaling (Self-Hosted)
- Related

## Overall Health

```dart
// Dart (Server SDK with admin privileges)
final health = await health.get();

print(health.status);  // 'pass' or 'fail'
```

---

## Service Checks

### Database

```dart
final dbHealth = await health.getDB();
print(dbHealth.status);  // 'pass'
print(dbHealth.ping);    // Response time in ms
```

### Cache (Redis)

```dart
final cacheHealth = await health.getCache();
print(cacheHealth.status);
print(cacheHealth.ping);
```

### Storage

```dart
final storageHealth = await health.getStorage();
print(storageHealth.status);
```

### Antivirus

```dart
final avHealth = await health.getAntivirus();
print(avHealth.status);  // 'pass' if ClamAV running
```

---

## Queue Monitoring

Check bg job queues.

```dart
// All queues
final queuesHealth = await health.getQueues();

for (final queue in queuesHealth.queues) {
    print('${queue.name}: ${queue.size} jobs');
}
```

### Specific Queues

```dart
final webhooks = await health.getQueueWebhooks();
final functions = await health.getQueueFunctions();
final builds = await health.getQueueBuilds();
final messaging = await health.getQueueMessaging();
final migrations = await health.getQueueMigrations();
```

---

## Certificate Check

Verify SSL cert valid.

```dart
final certHealth = await health.getCertificate(domain: 'cloud.appwrite.io');

print(certHealth.valid);        // true
print(certHealth.domain);       // cloud.appwrite.io
print(certHealth.signatureType); // RSA
print(certHealth.validFrom);    // ISO date
print(certHealth.validTo);      // ISO date
```

---

## Time Sync

Check server time accuracy.

```dart
final timeHealth = await health.getTime();

print(timeHealth.remoteTime);      // NTP server time
print(timeHealth.localTime);       // Server time
print(timeHealth.diff);            // Difference in ms
```

Time diff >30s break auth.

---

## Public Cloud Note

Health endpoints need admin API key. Cloud managed internally — endpoints self-hosted only.

---

## Monitoring Integration

Health check uses:

- **Uptime monitors:** Pingdom, UptimeRobot
- **Kubernetes probes:** Liveness/readiness
- **Alerting:** PagerDuty, Slack notifications
- **Dashboards:** Grafana, Datadog

### Example Endpoint

```typescript
// TypeScript - Express health endpoint
app.get('/health', async (req, res) => {
    try {
        const db = await health.getDB();
        const cache = await health.getCache();
        
        if (db.status === 'pass' && cache.status === 'pass') {
            res.status(200).json({ status: 'healthy' });
        } else {
            res.status(503).json({ status: 'degraded', db, cache });
        }
    } catch (e) {
        res.status(503).json({ status: 'unhealthy', error: e.message });
    }
});
```

---

## Horizontal Scaling (Self-Hosted)

Appwrite = many Docker containers. Stateless scale by replication; stateful need cluster config.

### What to Scale

| Container | Stateless? | How to Scale |
|-----------|-----------|--------------|
| API (appwrite) | Yes | Replicate + load balancer (Nginx/Traefik/HAProxy) |
| Function workers | Yes | Replicate freely |
| Realtime workers | Yes | Replicate freely |
| Other workers (webhooks, messaging, builds) | Yes | Replicate freely |
| MariaDB | No | Primary-replica replication |
| Redis | No | Redis Sentinel or Cluster |
| Storage volumes | No | Shared filesystem (NFS) or S3-compatible |

### Scale Stateless Containers

```bash
docker compose up --scale appwrite-worker-functions=4 -d
```

Route traffic through load balancer. Inter-container comms via Docker env vars.

### Performance Tuning

```bash
# Workers per CPU core (applies to API, Realtime, Executor containers)
_APP_WORKER_PER_CORE=6  # default, tune based on workload
```

### Stateful Containers

**MariaDB:** Primary-replica replication. Writes → primary; reads → replicas.

**Redis:** Sentinel for failover, Cluster for sharding. Redis = cache + pub/sub (Realtime). Set mem limits prevent OOM:

```bash
maxmemory 256mb
maxmemory-policy allkeys-lru
```

**Storage:** Switch local → S3-compatible (`_APP_STORAGE_DEVICE=s3`) so all nodes share files. Local disk = single node only.

### Monitoring Scaled Deployments

Use health endpoints per container. Route health checks via load balancer catch bad nodes.

Full self-hosting guide (install, backups, updates, maintenance): [self-hosting.md](self-hosting.md).

---

## Related

- Functions for health check automation
- Webhooks for alerting
- [performance.md](performance.md) — Redis caching patterns