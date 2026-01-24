## Quickstart

Open 2 terminals. 

Cd both to project root:
cd "C:\Users\Max\Desktop\projects\quanticon"

In the first terminal, run:
```
streamlit run ./ivy_bt/src/dashboard/Home.py
```

In the 2nd terminal, run:
```
python ./ivy_bt/src/api/main.py
```

That should start both parts of the project for the UI.

## Running things in the terminal

```
cd "C:/Users/Max/Desktop/projects/quanticon/ivy_bt/batch_configs" && python gen_batch_yaml.py
```

Then copy and paste the command from the terminal that looks like it needs to run.

## Docker

Or run these commands:
```
cd quanticon/ivy_bt
docker-compose up --build
```

To stop the containers, you have a few options depending on how you started them:

1.  **If running in the current terminal** (you see the logs):
    *   Press `Ctrl + C`. This sends a stop signal. You may need to press it twice to force kill if they don't shut down gracefully.

2.  **To stop and remove containers** (Recommended for clean rebuild):
    *   Run: `docker-compose down`
    *   This stops the containers and removes the networks, but keeps your data volumes (backtests, logs) safe.

3.  **To just stop them** (keep container state):
    *   Run: `docker-compose stop`

After stopping, you can run `docker-compose up --build` to rebuild and start fresh.