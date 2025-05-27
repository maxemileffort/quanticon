# Quanticon Local Simulator

This repository contains the local development environment and simulator for the Quanticon project. Quanticon is an AI-ready web application designed to help users simulate and analyze trading strategies using Monte Carlo techniques and technical indicators.

## Purpose of the Local Simulator

The local simulator, built with Streamlit, serves as a development and testing ground for the core machine learning and backtesting logic of the Quanticon application. It allows developers to rapidly iterate on data preparation, feature engineering, model training, and backtesting strategies without the need for the full web application infrastructure.

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd quanticon/local
    ```
2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv .venv
    ```
3.  **Activate the virtual environment:**
    -   On Windows:
        ```bash
        .venv\Scripts\activate
        ```
    -   On macOS/Linux:
        ```bash
        source .venv/bin/activate
        ```
4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## How to Run the Simulator

1.  Ensure your virtual environment is activated.
2.  Navigate to the `local` directory if you are not already there.
3.  Run the Streamlit application:
    ```bash
    streamlit run streamlit_app/app.py
    ```
4.  The simulator will open in your web browser.

## Overview of the ML Pipeline

The local simulator demonstrates the core machine learning pipeline for strategy simulation:

1.  **Data Fetching:** Downloads historical financial data using `yfinance`.
2.  **Data Preparation:** Generates technical indicators as features and defines target labels based on the desired ROI.
3.  **Model Training:** Trains an XGBoost model to predict target label occurrences.
4.  **Backtesting:** Simulates trading based on model predictions and calculates performance metrics.
5.  **Visualization:** Plots equity curves and visualizes trades on price charts.

## Current Status and TODOs

The local simulator currently implements a basic version of the ML pipeline. Key areas for future development and improvement are tracked in the `local/TODO.md` file. Refer to that file for a detailed list of pending tasks.

## Project Specification

For a comprehensive overview of the entire Quanticon project, including the web application, user roles, features, and deployment preferences, please refer to the main project specification: `spec.txt`.
