#!/usr/bin/env python3
"""
Quick Start Guide for Dublin AI Smart Mobility Planner

This script sets up and launches the agentic travel planning system.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


def print_header(text):
    """Print section header."""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")


def check_python():
    """Check Python version."""
    print("✓ Python version:", sys.version.split()[0])
    if sys.version_info < (3, 8):
        print("✗ Python 3.8+ required")
        sys.exit(1)


def check_dependencies():
    """Check if required packages are installed."""
    print_header("Checking Dependencies")
    
    required = [
        ("langchain", "LangChain"),
        ("langgraph", "LangGraph"),
        ("streamlit", "Streamlit"),
        ("pandas", "Pandas"),
    ]
    
    missing = []
    for module, name in required:
        try:
            __import__(module)
            print(f"✓ {name} installed")
        except ImportError:
            print(f"✗ {name} missing")
            missing.append(module)
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print("\nTo install, run:")
        print(f"  pip install -r requirements-agent.txt")
        return False
    
    return True


def check_otp():
    """Check if OTP server is running."""
    print_header("Checking OpenTripPlanner Server")
    
    try:
        import requests
        response = requests.get(
            "http://localhost:8080/otp/routers/default/plan",
            params={"fromPlace": "53.35,-6.25", "toPlace": "53.38,-6.27"},
            timeout=2
        )
        if response.status_code in [200, 400]:  # 400 is OK if params were bad
            print("✓ OTP server is running on localhost:8080")
            return True
    except Exception as e:
        pass
    
    print("✗ OTP server not found")
    print("\n  Make sure OTP is running:")
    print("    cd otp")
    print("    java -Xmx4G -jar otp-shaded.jar --build graphs/ --serve")
    return False


def check_llm():
    """Check LLM availability."""
    print_header("Checking LLM Backend")
    
    # Check Ollama first
    try:
        import requests
        response = requests.get("http://localhost:11434/api/models", timeout=2)
        if response.status_code == 200:
            print("✓ Ollama is running (localhost:11434)")
            print("  Available models:")
            import json
            models = json.loads(response.text).get("models", [])
            if models:
                for model in models[:3]:
                    print(f"    - {model['name']}")
            else:
                print("    (no models installed yet)")
            return True
    except Exception:
        pass
    
    # Check OpenAI
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            print("✓ OpenAI API key found")
            print(f"  Key: {api_key[:20]}...")
            return True
    except Exception:
        pass
    
    print("✗ No LLM backend found")
    print("\n  To use local LLM (free):")
    print("    1. Install Ollama from https://ollama.ai")
    print("    2. Run: ollama pull mistral")
    print("    3. Run: ollama serve")
    print("\n  OR to use OpenAI (paid):")
    print("    export OPENAI_API_KEY=\"sk-...\"")
    return False


def check_event_data():
    """Check event data availability."""
    print_header("Checking Event Data")
    
    events_path = Path("data/features/event_demand.csv")
    
    if events_path.exists():
        try:
            import pandas as pd
            df = pd.read_csv(events_path, engine="python", encoding_errors="replace")
            print(f"✓ Event data found: {len(df)} records")
            print(f"  Events: {df['event_name'].nunique()} unique")
            print(f"  Date range: {df['start_date'].min()} to {df['start_date'].max()}")
            return True
        except Exception as e:
            print(f"✗ Error reading event data: {e}")
            return False
    
    print("✗ Event data not found at data/features/event_demand.csv")
    return False


def launch_chat():
    """Launch the Streamlit chat interface."""
    print_header("Launching Chat Interface")
    
    print("Starting Streamlit app...")
    print("🌐 Opening http://localhost:8501\n")
    
    try:
        subprocess.run(
            ["streamlit", "run", "dashboard/chat.py"],
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
    except KeyboardInterrupt:
        print("\n\n👋 Chat interface closed")
    except FileNotFoundError:
        print("✗ Streamlit not found. Install with:")
        print("  pip install streamlit")


def main():
    """Main startup sequence."""
    print("\n")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║                                                                    ║")
    print("║     🚀 Dublin AI Smart Mobility Planner - Quick Start              ║")
    print("║                                                                    ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    
    # Checks
    print_header("Pre-Launch Checks")
    check_python()
    
    all_ok = True
    all_ok = check_dependencies() and all_ok
    all_ok = check_otp() and all_ok
    all_ok = check_llm() and all_ok
    all_ok = check_event_data() and all_ok
    
    if not all_ok:
        print_header("⚠️  Some requirements are missing")
        print("Please address the issues above and try again.")
        sys.exit(1)
    
    print_header("✅ All checks passed!")
    print("System is ready to launch.\n")
    
    # Launch
    response = input("Launch chat interface now? (y/n): ").strip().lower()
    if response == "y":
        launch_chat()
    else:
        print("\nTo launch later, run:")
        print("  streamlit run dashboard/chat.py")


if __name__ == "__main__":
    main()
