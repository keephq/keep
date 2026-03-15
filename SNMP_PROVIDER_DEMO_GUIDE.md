# SNMP Provider - Complete Beginner's Guide

## What is this?

This guide shows you how to receive **SNMP traps** (alerts from network devices) into **Keep**.

**Example:** Your server's monitoring system sends "CPU is too high!" → Keep receives it → You see it as an alert.

---

## Part 1: What You Need

### Prerequisites
1. A computer with Docker installed
2. A terminal/command prompt

---

## Part 2: Start Keep (If Not Running)

### Option A: Quick Start (Using Docker)

```bash
# Clone Keep repository
git clone https://github.com/keephq/keep.git
cd keep

# Start Keep with Docker
docker-compose up -d
```

### Option B: If Keep is Already Running
Skip to Part 3.

**Verify Keep is running:**
Open your browser and go to: `http://localhost:3000`

You should see the Keep dashboard. If not, wait 1 minute and refresh.

---

## Part 3: Install SNMP Provider

### Step 1: Login to Keep
1. Open `http://localhost:3000` in your browser
2. Login (create account if needed)

### Step 2: Find SNMP Provider
1. Click **"Providers"** in the left sidebar
2. In the search box, type **"SNMP"**
3. Click on the **SNMP** provider card

### Step 3: Configure Provider
Fill in the form:

| Field | Value |
|-------|-------|
| **Name** | `snmp-receiver` |
| **Host** | `127.0.0.1` |
| **Port** | `162` |
| **Community** | `public` |
| **OID** | `1.3.6.1.4.1.12345.1.2.3` |

Click **"Connect"**

### Step 4: Verify Connection
- You should see "Connected" message
- The provider appears in your providers list

---

## Part 4: Get Webhook URL (For Receiving Traps)

### What is a Webhook?
A webhook is just a URL where external systems can send data.

### Get Your Webhook URL

1. Go to **Providers** page
2. Click on your **`snmp-receiver`** provider
3. Look for **"Push alerts from SNMP"** section
4. **Copy** the webhook URL

It looks like:
```
https://your-keep-server.com/alerts/event/snmp?provider_id=xxx&api_key=xxx
```

**Save this URL!** You'll need it for the next step.

---

## Part 5: Send Test Trap (Simulate External System)

### Using curl (Linux/Mac/Windows)

Open a terminal and run:

```bash
curl -X POST "http://localhost:8080/alerts/event/snmp?provider_id=YOUR_PROVIDER_ID&api_key=YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "oid": "1.3.6.1.4.1.12345.1.2.3",
    "message": "CPU usage is high on server01",
    "source": "server01",
    "severity": "critical"
  }'
```

### Using PowerShell (Windows)

```powershell
$url = "http://localhost:8080/alerts/event/snmp?provider_id=YOUR_PROVIDER_ID&api_key=YOUR_API_KEY"

$body = @{
    oid      = "1.3.6.1.4.1.12345.1.2.3"
    message  = "CPU usage is high on server01"
    source   = "server01"
    severity = "critical"
} | ConvertTo-Json

Invoke-RestMethod -Uri $url -Method Post -ContentType "application/json" -Body $body
```

**Important:** Replace:
- `YOUR_PROVIDER_ID` - the provider ID from the webhook URL
- `YOUR_API_KEY` - the API key from the webhook URL

### If it works, you'll see:
```json
{"task_name":"some-task-id"}
```

---

## Part 6: See the Alert

1. Go to **Alerts** in Keep sidebar
2. Look for your new alert
3. You should see:
   - **Name:** "CPU usage is high on server01"
   - **Severity:** CRITICAL (red)
   - **Source:** ["snmp", "server01"]
   - **Provider:** snmp-receiver

---

## Part 7: Try Different Severities

### Critical
```bash
curl -X POST "http://localhost:8080/alerts/event/snmp?provider_id=xxx&api_key=xxx" \
  -H "Content-Type: application/json" \
  -d '{"message": "Critical alert", "severity": "critical"}'
```

```powershell
$body = @{ message = "Critical alert"; severity = "critical" } | ConvertTo-Json
Invoke-RestMethod -Uri $url -Method Post -ContentType "application/json" -Body $body
```

### Warning
```bash
curl -X POST "http://localhost:8080/alerts/event/snmp?provider_id=xxx&api_key=xxx" \
  -H "Content-Type: application/json" \
  -d '{"message": "Disk space low", "severity": "warning"}'
```

```powershell
$body = @{ message = "Disk space low"; severity = "warning" } | ConvertTo-Json
Invoke-RestMethod -Uri $url -Method Post -ContentType "application/json" -Body $body
```

### Info
```bash
curl -X POST "http://localhost:8080/alerts/event/snmp?provider_id=xxx&api_key=xxx" \
  -H "Content-Type: application/json" \
  -d '{"message": "System backup completed", "severity": "info"}'
```

```powershell
$body = @{ message = "System backup completed"; severity = "info" } | ConvertTo-Json
Invoke-RestMethod -Uri $url -Method Post -ContentType "application/json" -Body $body
```

---

## Part 8: Connect Real SNMP System (Zabbix, Nagios, etc.)

**Answer: YES, this is OUTSIDE of Keep!**

This step connects your **existing monitoring systems** (like Zabbix, Nagios, SolarWinds, etc.) to send alerts to Keep.

### What is this?
Your Zabbix/Nagios server is already monitoring your infrastructure. Instead of just sending emails, you can now also send alerts to Keep using the webhook URL.

### How it works:
```
Your Zabbix/Nagios → HTTP POST (JSON) → Keep → Alert in Keep
```

### For Zabbix Users:

1. Go to **Zabbix → Administration → Media Types → Create Media Type**
2. Settings:
   - **Name:** Keep SNMP
   - **Type:** Webhook
   - **URL:** `http://YOUR_KEEP_SERVER/alerts/event/snmp?provider_id=YOUR_PROVIDER_ID&api_key=YOUR_API_KEY`
   - **HTTP method:** POST
   - **Content type:** application/json
3. In "Parameters", add:
   ```
   {"message": "{ALERT.MESSAGE}", "source": "{HOST.NAME}", "severity": "{TRIGGER.SEVERITY}", "oid": "{ITEM.ID}"}
   ```
4. Create an **Action** to send notifications to this media type

### For Nagios Users:

In your Nagios configuration, set up a **HTTP notification command**:

```bash
define command{
    command_name    keep-notify
    command_line    /usr/bin/curl -X POST "http://YOUR_KEEP_SERVER/alerts/event/snmp?provider_id=YOUR_PROVIDER_ID&api_key=YOUR_API_KEY" -H "Content-Type: application/json" -d '{"message": "$HOSTNAME$ - $SERVICEDESC$ is $SERVICESTATE$", "source": "$HOSTNAME$", "severity": "critical"}'
}
```

### For Any Other System:

Configure your system to send HTTP POST requests to the webhook URL with this JSON body:

```json
{
  "oid": "1.3.6.1.4.1.12345.1.2.3",
  "message": "Alert message",
  "source": "hostname",
  "severity": "critical"
}
```

---

## Troubleshooting

### "Connection refused" error
- Make sure Keep is running: `docker-compose ps`
- Check correct port (8080 for API, 3000 for UI)

### "Provider not found" error
- Make sure you installed the SNMP provider first

### "Authentication failed" error
- Check your API key in the webhook URL
- Make sure the provider is connected

### No alert appears
- Check Keep logs: `docker-compose logs -f api`
- Verify curl response showed task_name

---

## Quick Reference

### Webhook URL Format
```
https://SERVER/alerts/event/snmp?provider_id=PROVIDER_ID&api_key=API_KEY
```

### JSON Payload Format
```json
{
  "oid": "1.3.6.1.4.1.12345.1.2.3",      // Optional: Object ID
  "message": "Alert message here",         // Required: Alert name
  "source": "server01",                   // Optional: Source hostname
  "severity": "critical",                 // Optional: critical|error|high|warning|medium|low|info
  "timestamp": "2024-01-15T10:30:00Z"    // Optional: Time
}
```

### Severity Mapping
| Incoming | Keep Severity |
|----------|---------------|
| critical | 🔴 CRITICAL |
| error | 🟠 HIGH |
| high | 🟠 HIGH |
| warning | 🟡 WARNING |
| medium | 🟡 WARNING |
| low | 🟢 LOW |
| info | ⚪ INFO |

---

## Done!

You now know how to:
1. ✅ Start Keep
2. ✅ Install SNMP provider
3. ✅ Get webhook URL
4. ✅ Send test traps (curl/PowerShell)
5. ✅ View alerts in Keep
6. ✅ Connect real systems (Zabbix, Nagios, etc.)

For more help, check: https://docs.keephq.dev
