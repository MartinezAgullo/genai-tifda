# TIFDA Integrations: Map Synchronization

This layer connects TIFDA's **in-memory COP** (the source of truth) with the **`mapa-puntos-interes`** visualization server (which uses PostgreSQL for persistence).

The system is built on two core components, both implemented as singletons.

```
┌─────────────────────────────────────────────────────────┐
│                    TIFDA (In-Memory COP)                │
│                   Source of Truth                       │
└─────────────────────┬───────────────────────────────────┘
                      │
                      │ COPSync
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│            mapa-puntos-interes                          │
│         (Visualization + PostgreSQL)                    │
└─────────────────────────────────────────────────────────┘
```

---

## 💻 Components Summary

### 1. `MapaClient` (Low-Level HTTP)
A robust **HTTP client** that handles direct communication with the `mapa-puntos-interes` REST API.

![mapa-puntos-interes-ui](https://github.com/MartinezAgullo/mapa-puntos-interes/blob/main/public/images/map-with-app6.png)

* **Key Features:** Provides full CRUD (Create/Read/Update/Delete) functionality, including powerful **Upsert** (create-or-update) and **Batch** operations.
* **Reliability:** Implements automatic **retry logic** with exponential backoff for timeouts and server (5xx) errors, and uses **connection pooling** for efficiency.

### 2. `COPSync` (High-Level Manager)
The synchronization manager that sits atop the `MapaClient`.

* **Role:** Manages the flow of data from TIFDA's `EntityCOP` objects to the map server's specific data format.
* **Sync Modes:** Supports syncing **single entities**, **batches**, or the **full COP state**. It also handles entity **removal** and tracks synchronization **statistics**.

---

## 🔄 Synchronization Patterns

The integration supports flexible deployment patterns:

1.  **Real-time Sync (Recommended):** Entities are synced immediately after creation or update in the COP using `sync_batch` (fast and non-blocking).
2.  **Periodic Full Sync:** A background thread pushes the entire COP state at regular intervals.


![mapa-puntos-interes-hoz](https://github.com/MartinezAgullo/genai-tifda/blob/main/assets/images/app_6_neutral.png)



---

## ⚙️ Configuration & Reliability

* **Error Handling:** Failures in map synchronization (e.g., connection refusal, timeouts) are generally **non-critical** to the main TIFDA pipeline. The client handles these via **automatic retries**.
* **Performance:** Performance is optimized by enforcing the use of **batch operations** and leveraging the client's built-in **connection pooling**.
* **Extensibility:** The system is designed for future enhancements, including bi-directional sync and integration with other Battle Management Systems (BMS).