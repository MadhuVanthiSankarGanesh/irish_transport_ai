# 🚀 Setup & Troubleshooting Guide

## Quick Start (3 Steps)

### Step 1: Install Dependencies
```bash
pip install -r requirements-agent.txt
```

### Step 2: Start LLM Backend

**Option A: Ollama (Free, Recommended)**
```bash
# 1. Download from https://ollama.ai
# 2. Install and run Ollama
ollama serve

# In another terminal:
ollama pull mistral
```

**Option B: OpenAI (Paid)**
```bash
# Set API key
export OPENAI_API_KEY="sk-your-api-key-here"
```

### Step 3: Run Agent
```bash
# Verify setup
python test_agent.py

# Launch chat interface
streamlit run dashboard/chat.py
```

---

## Troubleshooting

### ❌ "No module named 'state'" or Import Errors

**Solution:**
```bash
# Make sure you're in the project root
cd e:\irish_transport_ai

# Run commands from there
python test_agent.py
streamlit run dashboard/chat.py
```

### ❌ "OTP Connection - Status 404"

**The OTP server isn't running or not properly configured.**

**Solution:**
```bash
# 1. Start OTP (in new terminal)
cd otp
java -Xmx4G -jar otp-shaded.jar --build graphs/ --serve

# 2. Wait for it to start (1-2 minutes)
# 3. Check it's working:
curl "http://localhost:8080/otp/routers/default/plan?fromPlace=53.35,-6.25&toPlace=53.38,-6.27"

# 4. If that returns JSON with "plan", OTP is working
```

If you don't have OTP installed:
- Download from: http://docs.opentripplanner.org/
- Or skip this for now (agent can work without it)

### ❌ "LLM available - Neither Ollama nor OpenAI configured"

**You need to start one LLM backend.**

**Solution A: Use Ollama (Free)**
```bash
# Install from https://ollama.ai
ollama serve

# Wait for "Listening on 127.0.0.1:11434"
# Then test:
curl http://localhost:11434/api/models
```

**Solution B: Use OpenAI API**
```bash
# Get key from https://platform.openai.com/api-keys

# Set environment variable
export OPENAI_API_KEY="sk-..."

# Or add to .env file
echo 'OPENAI_API_KEY=sk-...' > .env
```

### ❌ "Connection refused" when running tests

**Something isn't running that the test expects.**

**Quick fix:**
```bash
# 1. Just focus on what works
python test_agent.py

# 2. Ignore OTP & LLM connection tests for now
# 3. Start LLM and OTP separately

# Terminal 1: LLM
ollama serve

# Terminal 2: OTP 
cd otp && java -Xmx4G -jar otp-shaded.jar --build graphs/ --serve

# Terminal 3: Run app
streamlit run dashboard/chat.py
```

---

## Minimal Setup (Works Without OTP)

If you don't want to bother with OTP setup, you can use the agent for:
- Event discovery
- Intent classification
- Geocoding
- Mock routing (uses simulated paths)

```bash
# Just needs LLM
ollama serve &
python test_agent.py
streamlit run dashboard/chat.py
```

---

## Configuration Files

### .env (Optional)
```bash
# Create in project root
OPENAI_API_KEY=sk-your-key-here
OTP_URL=http://localhost:8080/otp/routers/default
```

### config.yaml (Optional)
Edit to customize:
- LLM model (mistral, neural-chat, gpt-4o-mini, etc.)
- Temperature settings
- Response formatting
- Caching behavior

---

## Testing Individual Components

### Test Event Search Only
```python
from src.llm.tools import get_events_tool
result = get_events_tool("this_weekend", limit=5)
print(result)
```

### Test Geocoding
```python
from src.llm.tools import geocode_tool
result = geocode_tool("Trinity College Dublin")
print(result)
```

### Test OTP Routing
```python
from src.llm.tools import plan_route_tool
result = plan_route_tool(
    origin="53.35,-6.25",
    destination="53.38,-6.27",
)
print(result)
```

### Test Agent Directly
```python
from src.llm.agent_runner import create_agent
from langchain_community.llms import Ollama

llm = Ollama(model="mistral")
agent = create_agent(llm)
state, response = agent.process_input("What events this weekend?")
print(response)
```

---

## Port Requirements

Make sure these ports are available:
- **8501** - Streamlit app
- **11434** - Ollama (local LLM)
- **8080** - OTP server
- **6379** - Redis cache (optional)

```bash
# Check if ports are free
netstat -ano | findstr :8501
netstat -ano | findstr :11434
netstat -ano | findstr :8080
```

---

## Performance Tips

### Speed Up Tests
```bash
# Skip slow tests
python -c "from test_agent import test_imports, test_data_files; test_imports(); test_data_files()"
```

### Faster LLM Responses
- Use smaller model: `ollama pull neural-chat` (faster)
- Lower temperature in config.yaml

### Cache Events Data
```python
import time
from src.llm.tools import get_events_tool

# First call: slow (hits CSV)
events = get_events_tool("this_weekend")

# Second call: fast (cached in memory)
time.sleep(0.1)
events = get_events_tool("this_weekend")
```

---

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| `ModuleNotFoundError: state` | Wrong import paths | Run from project root: `cd e:\irish_transport_ai` |
| OTP 404 error | Server not running | Start: `cd otp && java -Xmx4G -jar otp-shaded.jar --build graphs/ --serve` |
| LLM connection refused | No LLM running | Start: `ollama serve` or set `OPENAI_API_KEY` |
| Streamlit port in use | Port 8501 occupied | `streamlit run app.py --server.port 8502` |
| Memory error | Too much data in memory | Reduce cache TTL in config.yaml |
| Slow responses | LLM overloaded | Use smaller model or OpenAI API |

---

## Development Workflow

### 1. Start Services (Background)
```bash
# Terminal 1: Ollama
ollama serve

# Terminal 2: OTP
cd otp && java -Xmx4G -jar otp-shaded.jar --build graphs/ --serve
```

### 2. Run Tests
```bash
# Terminal 3
python test_agent.py
```

### 3. Launch App
```bash
streamlit run dashboard/chat.py
```

### 4. Try Examples
```bash
python examples.py
```

---

## Getting Help

### Check Logs
```bash
# Streamlit
streamlit run app.py --logger.level=debug

# Agent
python -c "import logging; logging.basicConfig(level=logging.DEBUG)"
```

### Read Documentation
- [AGENT_README.md](AGENT_README.md) - Full system documentation
- [IMPLEMENTATION.md](IMPLEMENTATION.md) - Architecture details
- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment

### Test Individual Modules
```bash
# Imports
python -c "from src.llm.state import *; print('State OK')"
python -c "from src.llm.tools import *; print('Tools OK')"
python -c "from src.llm.graph import *; print('Graph OK')"
```

---

## Next Steps

1. ✅ Get LLM working (Ollama or OpenAI)
2. ✅ Run tests: `python test_agent.py`
3. ✅ Launch chat: `streamlit run dashboard/chat.py`
4. 📚 Read AGENT_README.md for full features
5. 🚀 Deploy: See DEPLOYMENT.md
