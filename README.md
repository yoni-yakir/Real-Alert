# Real Alert 🚨 
### Real-time OSINT Analysis & Validation System for Rocket Alerts

**Real Alert** is a Python-based OSINT tool designed to monitor, analyze, and validate incoming rocket launch alerts in Israel. 

The system specializes in distinguishing between "Pre-Alerts" (early warnings) and "Red Color" (active sirens), applying a statistical logic engine to filter noise and predict impact probability for specific metropolitan areas, specifically focused on **Herzliya & Central District**.

## 🧠 Features
- **Dual-Client Architecture**: Uses Telethon to listen to raw signals and a Telegram Bot for delivery.
- **Statistical Filtering**: Automatically filters northern/southern noise and focused on vector-based logic (Dan + Sharon).
- **Validation Engine**: Self-auditing system that checks its own predictions against real-time hits.
- **Dynamic UI**: Full Admin/User command interface with Telegram Reply Keyboards.
- **Performance Logging**: Detailed logs for success/failure rates to refine the prediction algorithm.

## 🛠 Tech Stack
- **Language:** Python 3.9+
- **Library:** [Telethon](https://github.com/LonamiWebs/Telethon) (Telegram MTProto API)
- **Deployment:** Google Cloud Platform (GCP)
- **Environment:** Linux (Debian)