"""
Programmatic usage examples for the Travel Planning Agent.

Shows how to use the agent outside of Streamlit for testing, batch processing, etc.
"""

import sys
import os

# Add src to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def example_1_basic_usage():
    """Example 1: Basic event discovery and route planning."""
    print("\n" + "="*70)
    print("Example 1: Event Discovery → Route Planning")
    print("="*70 + "\n")
    
    # Initialize LLM
    try:
        from langchain_community.llms import Ollama
        llm = Ollama(model="mistral")
        print("✓ Using Ollama")
    except ImportError:
        try:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
            print("✓ Using OpenAI")
        except ImportError:
            print("✗ No LLM available")
            return
    
    # Create agent
    from src.llm.agent_runner import create_agent
    agent = create_agent(llm)
    
    # Conversation
    conversations = [
        "What events are happening this weekend?",
        "Show me the first one",
        "Starting from O'Connell Street",
    ]
    
    for user_input in conversations:
        print(f"👤 You: {user_input}")
        state, response = agent.process_input(user_input)
        print(f"🤖 Assistant:\n{response}\n")


def example_2_direct_route_planning():
    """Example 2: Direct route planning without event selection."""
    print("\n" + "="*70)
    print("Example 2: Direct Route Planning")
    print("="*70 + "\n")
    
    try:
        from langchain_community.llms import Ollama
        llm = Ollama(model="mistral")
    except ImportError:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    
    from src.llm.agent_runner import create_agent
    agent = create_agent(llm)
    
    # Single request
    user_input = "Plan a trip from Merrion Square to Croke Park for 2:30 PM"
    print(f"👤 You: {user_input}")
    
    state, response = agent.process_input(user_input)
    print(f"🤖 Assistant:\n{response}\n")
    
    # Check if route was planned
    if agent.get_current_route():
        route = agent.get_current_route()
        print(f"Route details:")
        print(f"  - Travel time: {route['travel_time']:.0f} min")
        print(f"  - Transfers: {route['transfers']}")
        print(f"  - Departure: {route['departure']}")


def example_3_tool_usage():
    """Example 3: Using tools directly (bypassing LLM)."""
    print("\n" + "="*70)
    print("Example 3: Direct Tool Usage")
    print("="*70 + "\n")
    
    from src.llm.tools import get_events_tool, plan_route_tool, geocode_tool
    
    # Get events
    print("Searching for events this weekend...")
    events_result = get_events_tool("this_weekend", limit=3)
    
    if events_result["success"]:
        print(f"Found {len(events_result['events'])} events:")
        for i, event in enumerate(events_result["events"], 1):
            print(f"  {i}. {event['name']} - {event['location']}")
        
        # Use first event for routing
        first_event = events_result["events"][0]
        dest_coords = f"{first_event['lat']},{first_event['lon']}"
        
        # Geocode origin
        print("\nGeocoding origin...")
        geo_result = geocode_tool("O'Connell Street, Dublin")
        
        if geo_result["success"]:
            origin_coords = f"{geo_result['lat']},{geo_result['lon']}"
            
            # Plan route
            print("Planning route...")
            route_result = plan_route_tool(
                origin=origin_coords,
                destination=dest_coords,
                preference="balanced"
            )
            
            if route_result["success"]:
                route = route_result["route"]
                print(f"\n✓ Route planned:")
                print(f"  - Travel time: {route['travel_time']:.0f} min")
                print(f"  - Walking: {route['walking_time']:.0f} min")
                print(f"  - Transfers: {route['transfers']}")
                print(f"  - Depart at: {route['departure']}")
                print(f"\nSteps:")
                for step in route["steps"][:3]:
                    print(f"  - {step}")
                if len(route["steps"]) > 3:
                    print(f"  ... and {len(route['steps']) - 3} more")


def example_4_multi_turn_conversation():
    """Example 4: Multi-turn conversation with context."""
    print("\n" + "="*70)
    print("Example 4: Multi-turn Conversation with Context")
    print("="*70 + "\n")
    
    try:
        from langchain_community.llms import Ollama
        llm = Ollama(model="mistral")
    except ImportError:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    
    from src.llm.agent_runner import create_agent
    agent = create_agent(llm)
    
    # Start conversation
    print("🤖 Assistant: Hello! I'm your Dublin transport assistant.")
    print("              What would you like help with today?\n")
    
    # Simulate multi-turn
    turns = [
        ("Tell me what's on in Dublin next week", "Event discovery"),
        ("Pick event #1 for me", "Event selection"),
        ("I'm starting from Temple Bar", "Origin setting"),
    ]
    
    for user_input, label in turns:
        print(f"[{label}]")
        print(f"👤 You: {user_input}")
        state, response = agent.process_input(user_input)
        print(f"🤖 Assistant:\n{response}\n")
        
        # Show current context
        event = agent.get_current_event()
        route = agent.get_current_route()
        
        if event:
            print(f"📍 Event selected: {event['name']}")
        if route:
            print(f"📍 Route planned: {route['departure']} → {route['arrival']}")
        print()


def example_5_batch_processing():
    """Example 5: Batch processing multiple queries."""
    print("\n" + "="*70)
    print("Example 5: Batch Processing")
    print("="*70 + "\n")
    
    try:
        from langchain_community.llms import Ollama
        llm = Ollama(model="mistral")
    except ImportError:
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    
    from src.llm.agent_runner import create_agent
    
    queries = [
        "What's happening this weekend?",
        "Events next week?",
        "I need to get from Heuston to Temple Bar",
    ]
    
    print("Processing multiple queries...\n")
    
    for query in queries:
        agent = create_agent(llm)  # New agent for each query
        state, response = agent.process_input(query)
        
        print(f"Query: {query}")
        print(f"Intent: {state.intent}")
        print(f"Response: {response[:100]}...\n" if len(response) > 100 else f"Response: {response}\n")


def main():
    """Run examples."""
    print("\n")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║                                                                    ║")
    print("║  Travel Planning Agent - Usage Examples                           ║")
    print("║                                                                    ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    
    examples = {
        "1": ("Basic event discovery → route planning", example_1_basic_usage),
        "2": ("Direct route planning", example_2_direct_route_planning),
        "3": ("Tool usage (bypassing LLM)", example_3_tool_usage),
        "4": ("Multi-turn conversation", example_4_multi_turn_conversation),
        "5": ("Batch processing", example_5_batch_processing),
    }
    
    print("\nAvailable examples:")
    for key, (desc, _) in examples.items():
        print(f"  {key}. {desc}")
    print("  0. Run all examples")
    print("  Q. Quit")
    
    choice = input("\nSelect example (0-5 or Q): ").strip().upper()
    
    if choice == "Q":
        return
    elif choice == "0":
        for _, func in examples.values():
            try:
                func()
            except Exception as e:
                print(f"\n✗ Error: {e}")
                import traceback
                traceback.print_exc()
    elif choice in examples:
        try:
            examples[choice][1]()
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Invalid choice")
    
    print("\n" + "="*70)
    print("Examples completed!")


if __name__ == "__main__":
    main()
