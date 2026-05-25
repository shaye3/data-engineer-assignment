# Senior Data Engineer — Home Assignment

**Estimated time:** 3–4 hours

---

## Background

You are joining a data engineering team that ingests sensor telemetry from a fleet of ships into a centralized analytics platform. Ships periodically generate JSON files containing sensor measurements (GPS) and upload them to an input location. Your job is to build the pipeline that gets that data into a queryable data store.

You are free to choose your own tools. What matters is how you design and orchestrate the pipeline.

The generator is already running inside the cluster, dropping JSON sensor files onto a shared PVC (`input-pvc`). You do not need to build or run the data source — just plug your pipeline into whatever is landing on that PVC.

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| kubectl | 1.28+ | https://kubernetes.io/docs/tasks/tools/ |
| minikube | 1.32+ | https://minikube.sigs.k8s.io/docs/start/ |
| Python | 3.10+ | https://python.org |

---

## Quick Start

```bash
# Clone the repo
git clone <repo-url>
cd <repo-name>

# Bootstrap the cluster (takes ~5 minutes)
chmod +x bootstrap.sh
./bootstrap.sh
```

This will:
1. Start minikube with 4 GB RAM and 4 CPUs
2. Install KEDA
3. Create the `sensor-pipeline` namespace and `input-pvc`
4. Build the generator Docker image and deploy it

Verify everything is running:

```bash
kubectl get pods -n sensor-pipeline
# NAME                         READY   STATUS    RESTARTS   AGE
# generator-xxxx-xxxx          1/1     Running   0          30s

kubectl logs deploy/generator -n sensor-pipeline
# [10:14:02] #0001  ship-03_gps_20260523T101400Z.json  (15 KB | 100 rows | 0.01s)
# [10:14:32] #0002  ship-07_gps_20260523T101432Z.json  (15 KB | 100 rows | 0.01s)
```

---

## Controlling the Generator

The generator runs as a Kubernetes Deployment inside the cluster. By default it produces small files (~15 KB) at 2 files/minute from 10 ships.

```bash
# Stop the generator
kubectl scale deployment generator -n sensor-pipeline --replicas=0

# Start the generator
kubectl scale deployment generator -n sensor-pipeline --replicas=1
```

To change the load profile, edit `generator/k8s/deployment.yaml` and update the env vars, then re-apply:

| Env var | Default | Options |
|---|---|---|
| `RATE` | `2` | files per minute |
| `SIZE` | `small` | `small` (~15 KB), `medium` (~5 MB), `large` (~45 MB) |
| `SOURCES` | `10` | number of distinct ship IDs |

```bash
kubectl apply -f generator/k8s/deployment.yaml
```

---

## Assignment

### Requirements

| Requirement | Detail |
|---|---|
| **Latency** | Up to 10–15 minutes from JSON file landing to data queryable in the target store. |
| **Scale** | The solution should be scalable, supporting multiple ship dumps and enabling parallel processing. |
| **Volume** | File sizes vary significantly and are unpredictable — support small and large files. Files are not evenly distributed across time or sources. |
| **Data completeness** | The output should include all the data from the source. |
| **Resource efficiency** | Compute resources are limited. The pipeline must make efficient use of CPU and memory. |
| **Concurrency** | Handle concurrent processing of multiple data sources simultaneously. |

### More Instructions

- The pipeline needs to run on **Kubernetes**
- Use **KEDA** for autoscaling
- Use **free and open-source** tools — no paid cloud services
- Local execution via **minikube** or **kind** is acceptable
- **Treat this as a production workflow.** Think about scenarios that could break the pipeline and handle them in code. Document the scenarios you chose to address in your README and justify your choices.
- The output should be stored in a queryable format

### Input Data

The generator produces JSON files. Each file contains an array of sensor records from one `source_id` and one `measurement` type:

```json
[
  {
    "source_id": "ship-42",
    "measurement": "gps",
    "timestamp": "2026-05-23T10:14:00Z",
    "values": {
      "lat": 32.08,
      "lon": 34.78,
      "speed_knots": 12.4
    }
  }
]
```

**File naming:** `{source_id}_{measurement}_{timestamp_utc}.json`  
**Example:** `ship-42_gps_20260523T101400Z.json`

Files land on `input-pvc` at `/input` inside the cluster. Your pipeline pods should mount this PVC to read them.

### You Decide

- How many stages the pipeline has and where the stage boundaries are
- Which message queue or trigger mechanism to use (RabbitMQ, Redis Streams, Kafka, Redpanda, Apache Pulsar, etc.)
- Which output storage and data format to use
- How to handle chunking, batching, and file sizing for your chosen data store

**The most critical aspect is managing autoscaling with KEDA to ensure efficient Kubernetes resource utilization while guaranteeing that no data is lost.**

### What to Deliver

1. **Working pipeline** — Git repo with all code, Kubernetes manifests, and configuration. Include a `README.md` so someone unfamiliar with your choices can run it.
2. **Design document (1–2 pages)** — Architecture, tool choices, failure handling, trade-offs, and what you'd change for 500+ sources.
3. **AI transcript** — The full conversation log from Claude Code, Cursor, Copilot, or any AI tool you used.

**Submission:** Send a link to your Git repo (GitHub, GitLab, or zip), the design document, and the AI transcript.

---

## Verifying Your Pipeline

`verify.py` counts input files vs output files and reports a per-source PASS/FAIL.

### Step 1 — Copy files from the cluster to local dirs

```bash
# Copy input files from the PVC (via the generator pod)
GENERATOR_POD=$(kubectl get pod -n sensor-pipeline -l app=generator -o jsonpath='{.items[0].metadata.name}')
kubectl cp sensor-pipeline/${GENERATOR_POD}:/input /tmp/input

# Copy your output files similarly (adjust pod name / path to your pipeline)
YOUR_POD=$(kubectl get pod -n sensor-pipeline -l app=<your-app> -o jsonpath='{.items[0].metadata.name}')
kubectl cp sensor-pipeline/${YOUR_POD}:/output /tmp/output
```

### Step 2 — Run verify

```bash
python verify.py --input-dir /tmp/input --output-dir /tmp/output
```

Example output:

```
Source           Input   Output   Status
---------------------------------------------
ship-01              8        8       OK
ship-02              6        6       OK
ship-03             10       10       OK
---------------------------------------------
TOTAL               24       24

Status: PASS
```

> You can also run `verify.py` inside the cluster via `kubectl exec` if you prefer not to copy files locally.
