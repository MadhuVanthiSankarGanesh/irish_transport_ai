"""
Test suite for the Travel Planning Agent.

Run tests to verify the system is working correctly.
"""

import sys
import os
import time
from pathlib import Path

# Add src to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def print_test_header(name):
    """Print test section header."""
    print(f"\n{'='*70}")
    print(f"  {name}")
    print('='*70)


def print_result(test_name, success, message=""):
    """Print test result."""
    status = "✓ PASS" if success else "✗ FAIL"
    print(f"{status}: {test_name}")
    if message:
        print(f"       {message}")


# ============================================================================
# TESTS
# ============================================================================

def test_imports():
    """Test that all required modules can be imported."""
    print_test_header("Import Tests")
    
    modules = [
        ("langchain", "LangChain"),
        ("langgraph", "LangGraph"),
        ("streamlit", "Streamlit"),
        ("pandas", "Pandas"),
        ("requests", "Requests"),
        ("geopy", "GeoPy"),
    ]
    
    results = []
    for module, name in modules:
        try:
            __import__(module)
            print_result(f"Import {name}", True)
            results.append(True)
        except ImportError as e:
            print_result(f"Import {name}", False, str(e))
            results.append(False)
    
    return all(results)


def test_data_files():
    """Test that required data files exist."""
    print_test_header("Data File Tests")
    
    files = [
        ("data/features/event_demand.csv", "Event data"),
        ("data/clean/stops.csv", "Stops reference"),
        ("data/clean/routes.csv", "Routes reference"),
    ]
    
    results = []
    for path, name in files:
        full_path = Path(BASE_DIR) / path
        exists = full_path.exists()
        size = f"({full_path.stat().st_size / 1024:.1f} KB)" if exists else ""
        print_result(f"File: {name}", exists, size)
        results.append(exists)
    
    return all(results)


def test_tool_modules():
    """Test that tool modules can be imported and initialized."""
    print_test_header("Tool Module Tests")
    
    try:
        from src.llm.state import AgentState, create_initial_state
        print_result("State module", True)
        
        state = create_initial_state()
        print_result("Create initial state", state is not None)
        
        from src.llm.tools import geocode_tool, get_events_tool, plan_route_tool
        print_result("Tools import", True)
        
        return True
    except Exception as e:
        print_result("Tool modules", False, str(e))
        return False


def test_event_search():
    """Test event search functionality."""
    print_test_header("Event Search Tests")
    
    try:
        from src.llm.tools import get_events_tool
        
        # Test this_weekend
        result = get_events_tool("this_weekend", limit=3)
        success = result["success"]
        count = len(result.get("events", []))
        print_result("Search this_weekend", success, f"Found {count} events")
        
        if success and count > 0:
            event = result["events"][0]
            has_fields = all(k in event for k in ["name", "location", "lat", "lon"])
            print_result("Event fields", has_fields)
            return has_fields
        
        return success
    
    except Exception as e:
        print_result("Event search", False, str(e))
        return False


def test_geocoding():
    """Test geocoding functionality."""
    print_test_header("Geocoding Tests")
    
    try:
        from src.llm.tools import geocode_tool
        
        # Test known location
        result = geocode_tool("Merrion Square, Dublin")
        success = result["success"]
        
        if success:
            print_result(
                "Geocode location",
                True,
                f"({result['lat']:.4f}, {result['lon']:.4f})"
            )
            return True
        else:
            print_result("Geocode location", False, result.get("error"))
            return False
    
    except Exception as e:
        print_result("Geocoding", False, str(e))
        return False


def test_otp_connection():
    """Test OTP server connection."""
    print_test_header("OTP Server Tests")
    
    try:
        import requests
        
        response = requests.get(
            "http://localhost:8080/otp/routers/default/plan",
            params={
                "fromPlace": "53.35,-6.25",
                "toPlace": "53.38,-6.27",
                "date": "2026-03-28",
                "time": "14:30"
            },
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            has_plan = "plan" in data and "itineraries" in data.get("plan", {})
            print_result("OTP connection", True)
            print_result("OTP response format", has_plan)
            return has_plan
        else:
            print_result("OTP connection", False, f"Status {response.status_code}")
            return False
    
    except requests.exceptions.ConnectionError:
        print_result(
            "OTP connection",
            False,
            "Cannot connect. Is OTP running on localhost:8080?"
        )
        return False
    except Exception as e:
        print_result("OTP connection", False, str(e))
        return False


def test_llm_connection():
    """Test LLM connection."""
    print_test_header("LLM Tests")
    
    # Try Ollama first
    try:
        import requests
        
        response = requests.get(
            "http://localhost:11434/api/models",
            timeout=5
        )
        
        if response.status_code == 200:
            import json
            models = json.loads(response.text).get("models", [])
            
            if models:
                print_result("Ollama connection", True, f"({len(models)} models)")
                return True
            else:
                print_result(
                    "Ollama models",
                    False,
                    "No models installed. Run: ollama pull mistral"
                )
                return False
    except requests.exceptions.ConnectionError:
        pass
    except Exception:
        pass
    
    # Try OpenAI
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        
        if api_key:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
            result = llm.invoke("Hello")
            
            print_result(
                "OpenAI connection",
                True,
                f"Key: {api_key[:10]}..."
            )
            return True
    except Exception as e:
        pass
    
    print_result(
        "LLM available",
        False,
        "Neither Ollama nor OpenAI configured"
    )
    return False


def test_graph_initialization():
    """Test that the LangGraph can be initialized."""
    print_test_header("Graph Initialization Tests")
    
    try:
        # Need to initialize a mock LLM first
        class MockLLM:
            def invoke(self, messages):
                class Response:
                    content = "EVENT_DISCOVERY"
                return Response()
        
        llm = MockLLM()
        
        from src.llm.graph import build_graph
        
        graph, app = build_graph(llm)
        print_result("Build graph", graph is not None)
        print_result("Compile app", app is not None)
        
        return True
    
    except Exception as e:
        print_result("Graph initialization", False, str(e))
        import traceback
        print(traceback.format_exc())
        return False


def test_end_to_end():
    """Test end-to-end agent flow."""
    print_test_header("End-to-End Test")
    
    try:
        # Try to initialize agent with real LLM
        try:
            from langchain_community.llms import Ollama
            llm = Ollama(model="mistral")
            llm_type = "Ollama"
        except:
            try:
                from langchain_openai import ChatOpenAI
                if not os.environ.get("OPENAI_API_KEY"):
                    raise ValueError("OPENAI_API_KEY not set")
                llm = ChatOpenAI(model="gpt-4o-mini")
                llm_type = "OpenAI"
            except:
                print_result("End-to-end", False, "No LLM available")
                return False
        
        from src.llm.agent_runner import create_agent
        
        start_time = time.time()
        agent = create_agent(llm)
        elapsed = time.time() - start_time
        
        print_result("Create agent", True, f"({elapsed:.2f}s)")
        
        # Test simple query (with timeout)
        start_time = time.time()
        try:
            state, response = agent.process_input(
                "What events are happening this weekend?"
            )
            elapsed = time.time() - start_time
            
            has_response = response and len(response) > 0
            print_result("Process query", has_response, f"({elapsed:.2f}s) using {llm_type}")
            
            return has_response
        
        except Exception as e:
            print_result("Process query", False, str(e))
            return False
    
    except Exception as e:
        print_result("End-to-end", False, str(e))
        import traceback
        print(traceback.format_exc())
        return False


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Run all tests."""
    print("\n")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║                                                                    ║")
    print("║  Travel Planning Agent - Test Suite                               ║")
    print("║                                                                    ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    
    tests = [
        ("Imports", test_imports),
        ("Data Files", test_data_files),
        ("Tool Modules", test_tool_modules),
        ("Event Search", test_event_search),
        ("Geocoding", test_geocoding),
        ("OTP Connection", test_otp_connection),
        ("LLM Connection", test_llm_connection),
        ("Graph Initialization", test_graph_initialization),
        ("End-to-End", test_end_to_end),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except KeyboardInterrupt:
            print("\n\n⚠️  Tests interrupted")
            break
        except Exception as e:
            print_result(f"Test: {test_name}", False, str(e))
            results[test_name] = False
    
    # Summary
    print_test_header("Test Summary")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓" if result else "✗"
        print(f"  {status} {test_name}")
    
    print(f"\n  Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All tests passed! System is ready to use.\n")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review issues above.\n")
        return 1


if __name__ == "__main__":
    exit(main())
