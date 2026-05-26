# Senior Data Engineer — Home Assignment

**Estimated time:** 3–4 hours

---

## Background

You are joining a data engineering team that ingests sensor telemetry from a fleet of ships into a centralized analytics platform. Ships periodically generate JSON files containing sensor measurements (GPS) and upload them to an input location. Your job is to build the pipeline that gets that data into a queryable data store.

You are free to choose your own tools. What matters is how you design and orchestrate the pipeline.

A data generator is provided. It runs as a Kubernetes Deployment inside the cluster and continuously drops JSON sensor files onto a shared PVC (`input-pvc`) at a configurable rate. You do not need to build the data source — just plug your pipeline into whatever lands at `/input` on that PVC.

---

## What you need to do

Create an ingestion date pipeline using Kubernetes and KEDA that ingests JSON files with sensor information and transforms the data into an efficient columnar format. 

**You decide:**
- How many stages the pipeline has and where the stage boundaries are
- Which message queue or trigger mechanism to use (RabbitMQ, Redis Streams, Kafka, Redpanda, Apache Pulsar etc.)
- How to handle chunking, batching, and file sizing for your chosen data store

**The most critical aspect is managing multiprocessing and autoscaling with KEDA to ensure efficient Kubernetes resource utilization while guaranteeing that no data is lost.**

---

## Requirements

| Requirement | Detail                                                                                                                                                    |
|---|-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Latency** | Up to 10–15 minutes from JSON file landing to data queryable in the target store.                                                                         |
| **Scale** | The solution should be scalable, supporting multiple ship dumps and enabling parallel processing.                                                         |
| **Volume** | File sizes vary significantly and are unpredictable, need to support small and large file sizes. Files are not evenly distributed across time or sources. |
| **Data completeness** | The output should include all the data from the source                                                                                                    |
| **Resource efficiency** | Compute resources are limited. The pipeline must make efficient use of CPU and memory                                                                     |
| **Concurrency** | Need to handle concurrent processing of multiple data sources simultaneously.                                                                             |

### More instructions

- The pipeline needs to run on **Kubernetes**
- Use **KEDA** for autoscaling
- Use **free and open-source** tools — no paid cloud services
- Local execution via **minikube** or **kind** is acceptable
- **Treat this as a production workflow.** The pipeline must be robust and stable. It is expected to think about scenarios that could break the pipeline and handle them in the code. Document the scenarios you chose to address in the README and justify your choices.
- The output should be stored in queriable format

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


## Input Data

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
  },
  ...
]
```

### File Naming

```
{source_id}_{measurement}_{timestamp_utc}.json

Example: ship-42_gps_20260523T101400Z.json
```

### Available Measurement Types

| Measurement | Fields in `values` |
|---|---|
| `gps` | `lat`, `lon`, `speed_knots` |

### Generator

The generator runs as a Kubernetes Deployment inside the cluster and writes files directly to `input-pvc`. It starts automatically when you run `./bootstrap.sh` — no local Python or open terminal required.

Files land at `/input` on the PVC. Your pipeline pods should mount `input-pvc` to read them.

**Control the generator:**

```bash
# Stop
kubectl scale deployment generator -n sensor-pipeline --replicas=0

# Start
kubectl scale deployment generator -n sensor-pipeline --replicas=1

# View live output
kubectl logs -f deploy/generator -n sensor-pipeline
```

**Change the load profile** — edit `generator/k8s/deployment.yaml` and update the env vars, then re-apply:

| Env var | Default | Options |
|---|---|---|
| `RATE` | `2` | files per minute |
| `SIZE` | `small` | `small` (~15 KB), `medium` (~5 MB), `large` (~45 MB) |
| `SOURCES` | `10` | number of distinct ship IDs |

```bash
kubectl apply -f generator/k8s/deployment.yaml
```

---

## Verifying Data Completeness

`verify.py` counts `.json` files per source in `--input-dir` and all files per source in `--output-dir`, then reports a per-source PASS/FAIL.

**How the pipeline works with verify.py:**
- The Processor moves processed `.json` files from `/input/` to `/input/done/` (not deleted) — so they remain countable
- Output Parquet files are written flat to `/output/` on `output-pvc`
- Run verify.py **after the pipeline has finished processing** all files (no pending messages in Redis)

**Step 1 — Stop the generator (so no new files arrive mid-check):**

```bash
kubectl scale deployment generator -n sensor-pipeline --replicas=0
```

**Step 2 — Wait for the pipeline to drain (all pending files processed):**

```bash
# Watch until no processor pods are running (scaled to zero by KEDA)
kubectl get pods -n sensor-pipeline -w
```

**Step 3 — Copy files from the cluster to local directories:**

```bash
# Processed input files (moved here by the processor after successful conversion)
GENERATOR_POD=$(kubectl get pod -n sensor-pipeline -l app=generator -o jsonpath='{.items[0].metadata.name}')
kubectl cp sensor-pipeline/${GENERATOR_POD}:/input/done /tmp/input

# Output Parquet files
PROCESSOR_POD=$(kubectl get pod -n sensor-pipeline -l app=processor -o jsonpath='{.items[0].metadata.name}')
kubectl cp sensor-pipeline/${PROCESSOR_POD}:/output /tmp/output
```

**Step 4 — Run the check:**

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

> **Note:** `verify.py` counts ALL files in `--output-dir` regardless of extension. Ensure no `.parquet.tmp` files remain in `/output/` before running — the pipeline cleans these up automatically on startup and on graceful shutdown.

> You can also run `verify.py` inside the cluster directly:
> ```bash
> kubectl exec -n sensor-pipeline ${PROCESSOR_POD} -- \
>   python /app/verify.py --input-dir /input/done --output-dir /output
> ```

---

## What You Need To Deliver

### 1. Working Pipeline

A Git repository containing all code, Kubernetes manifests, and configuration.

Include a `README.md` with setup instructions. Someone unfamiliar with your choices should be able to run the pipeline by following the README.

### 2. Design Document (1–2 pages)

A written document covering:
- Your pipeline architecture (stages, boundaries, data flow)
- Why you chose each tool (queue, storage, data store)
- How you handle failures — what happens if a stage crashes mid-processing?
- Trade-offs you made given the 3–4 hour time constraint
- What you would change for a production deployment at 500+ sources


### 3. AI Transcript

The complete conversation log from Claude Code, Cursor, Copilot, or any AI coding tool you used during the assignment.

We expect candidates to use AI tools. We want to see **how** you work with them. Export the full session


## Submission

Send us:
1. A link to your Git repository (GitHub, GitLab, or a zip file)
2. The design document (can be in the repo or a separate PDF)
3. The AI transcript file(s)

Good luck.
