# Deployment Guide for IvyBT

This guide outlines several free or low-cost ways to deploy the IvyBT backtesting engine.

## Option 1: Local Deployment with Docker (Recommended)

This is the easiest way to run the full stack (Dashboard + API) on your machine or a VPS without dependency conflicts.

**Prerequisites:**
- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- Docker Compose

**Steps:**

1.  **Build and Run**:
    Navigate to the project directory and run:
    ```bash
    docker-compose up --build
    ```

2.  **Access Services**:
    - **Dashboard**: Open `http://localhost:8501` in your browser.
    - **API**: The API is available at `http://localhost:8000` (Docs: `http://localhost:8000/docs`).

3.  **Persistence**:
    The `backtests`, `logs`, and `.cache` directories are mounted as volumes, so your data persists even if you restart the containers.

---

## Option 2: Streamlit Community Cloud (Free)

Best for hosting the **Dashboard** publicly if your repository is public.

**Prerequisites:**
- A GitHub account.
- The IvyBT repository pushed to GitHub.

**Steps:**

1.  Go to [share.streamlit.io](https://share.streamlit.io/).
2.  Connect your GitHub account.
3.  Click "New app".
4.  Select your repository, branch, and the main file path: `src/dashboard/Home.py`.
5.  Click "Deploy".

**Note**: The Streamlit Community Cloud instance is ephemeral. Files saved to disk (like backtest results) may disappear if the app restarts. For persistent storage, you would need to modify the code to use cloud storage (S3, Google Drive, etc.), but for a research tool, this might be acceptable.

---

## Option 3: Render (Free / Low Cost)

Render offers a free tier for Web Services, which is great for the **API**.

**Deploying the API:**

1.  Create a Render account.
2.  Click "New +", then "Web Service".
3.  Connect your GitHub repo.
4.  Settings:
    - **Runtime**: Python 3
    - **Build Command**: `pip install -r requirements.txt`
    - **Start Command**: `uvicorn src.api.main:app --host 0.0.0.0 --port 10000`
5.  Click "Create Web Service".

**Note**: The free tier spins down after 15 minutes of inactivity.

---

## Option 4: Low-Cost VPS (DigitalOcean, Hetzner, etc.)

For ~$5-6/month, you can have a dedicated server running both the Dashboard and API 24/7.

**Steps:**

1.  **Provision a Server**: Create a droplet/instance (Ubuntu 22.04 LTS is recommended).
2.  **Install Docker**:
    ```bash
    apt-get update
    apt-get install -y docker.io docker-compose
    ```
3.  **Clone Repository**:
    ```bash
    git clone https://github.com/yourusername/ivy_bt.git
    cd ivy_bt
    ```
4.  **Run**:
    ```bash
    docker-compose up -d
    ```
5.  **Access**:
    - Dashboard: `http://<your-server-ip>:8501`
    - API: `http://<your-server-ip>:8000`

**Security Tip**: For a production VPS, set up a firewall (`ufw`) and consider using a reverse proxy like Nginx with SSL (Let's Encrypt) to secure your endpoints.
