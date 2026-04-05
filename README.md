# Real Alert 🚨 [עברית](README-he.md)
### Real-time OSINT Analysis & Validation System for Rocket Alerts

**Real Alert** is a professional-grade Python-based OSINT tool designed to monitor, analyze, and validate incoming rocket launch alerts in Israel. 

The system specializes in distinguishing between "Pre-Alerts" (early warnings) and "Red Color" (active sirens), applying a statistical logic engine to filter noise and predict impact probability for specific metropolitan areas, specifically focused on **Herzliya & Central District**.

## 📍 Live Demo
Experience the system on Telegram: [@herzliya_alerts_bot](https://t.me/herzliya_alerts_bot)  
*(Note: Real-time push notifications require physical presence in the Herzliya/Ramat HaSharon area via Geo-Location validation).*

## 🧠 Features
- **Dual-Client Architecture**: Leverages Telethon to listen to raw signals and a dedicated Bot API for user delivery.
- **Geo-Fencing Onboarding**: Integrated location-based validation to ensure alert relevance and server resource optimization.
- **Statistical Filtering**: Automatically filters regional noise (Northern/Southern vectors) using Dan-Sharon focused logic.
- **Validation Engine**: A self-auditing module that validates predictions against real-time hits for continuous algorithm refinement.
- **Admin Dashboard**: Remote management of users and system logs directly through Telegram's interface.

## 🛰 Geo-Fencing & Location Logic
To prevent alert fatigue and ensure hyper-local accuracy, the system implements a **Bounding Box** validation method. Users must share their live location to subscribe to push alerts.



The "Subscription Zone" is surgically defined by the following coordinates:
* **North:** 32.1807 (Nachlat Ada)
* **South:** 32.1527 (Ramat HaSharon)
* **East:** 34.8638 (Neve Amal)
* **West:** 34.8208 (Elon St.)

**Privacy Note:** GPS coordinates are processed in real-time to verify the boundary and are **never stored** in the database. Only the User ID is retained for delivery.

## 🛠 Tech Stack
- **Language:** Python 3.9+
- **Core Library:** [Telethon](https://github.com/LonamiWebs/Telethon) (MTProto API)
- **Deployment:** Google Cloud Platform (GCP)
- **Environment:** Linux (Debian 12)
- **Configuration:** Environment-based (Dotenv) for secure API management.

## 📊 Logic Flow
1. **Listen:** Continuously monitor `tzevaadomm` raw data stream.
2. **Filter:** Discard non-Central/Sharon alerts.
3. **Analyze:** Evaluate "Pre-Alert" complexity to predict impact probability.
4. **Validate:** Match predictions with subsequent "Red Color" sirens for accuracy logging.