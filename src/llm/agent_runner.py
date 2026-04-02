"""
Runner for the travel planning agent graph.

Provides simple interface to run the agent and manage conversations.
"""

import logging
from typing import Optional, Tuple
from datetime import datetime
from src.llm.state import AgentState, add_message, create_initial_state
from src.llm.graph import build_graph

logger = logging.getLogger(__name__)


class TravelPlanningAgent:
    """
    Main agent runner for the travel planning system.
    
    Manages state, conversation history, and graph execution.
    """
    
    def __init__(self, llm):
        """Initialize the agent with an LLM."""
        self.llm = llm
        self.graph = None
        self.app = None
        self.state = None
        self.conversation_history = []
        
        # Build graph
        self._initialize_graph()
    
    def _initialize_graph(self):
        """Initialize the LangGraph."""
        try:
            self.graph, self.app = build_graph(self.llm)
            logger.info("Graph initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize graph: {e}")
            raise
    
    def start_conversation(self) -> AgentState:
        """
        Start a new conversation.
        
        Returns:
            Initial agent state
        """
        self.state = create_initial_state()
        self.conversation_history = []
        return self.state
    
    def process_input(self, user_input: str) -> Tuple[AgentState, str]:
        """
        Process a single user input through the agent.
        
        Args:
            user_input: The user's message
        
        Returns:
            (updated_state, response_text)
        """
        if self.state is None:
            self.start_conversation()
        
        try:
            # Record user input
            self.state.last_user_input = user_input
            self.state = add_message(self.state, "user", user_input)
            
            # Clear response for new turn
            self.state.response = None
            
            # Run graph
            logger.info(f"Processing input: {user_input[:50]}...")
            
            # Invoke the app with the state
            result = self.app.invoke(self.state)
            
            # Extract result from LangGraph (it returns a dict)
            if isinstance(result, AgentState):
                self.state = result
            elif isinstance(result, dict):
                # Update state with result dict
                for key, value in result.items():
                    if hasattr(self.state, key):
                        setattr(self.state, key, value)
            
            # Record assistant response
            response_text = self.state.response
            if not response_text:
                logger.warning(f"No response generated. State: intent={self.state.intent}, response={self.state.response}")
                response_text = "No response generated"
            self.state = add_message(self.state, "assistant", response_text)
            
            # Store in conversation history
            self.conversation_history.append({
                "user": user_input,
                "assistant": response_text,
                "timestamp": datetime.now().isoformat()
            })
            
            logger.info(f"Response generated. Intent: {self.state.intent}")
            
            return self.state, response_text
        
        except Exception as e:
            logger.error(f"Error processing input: {e}")
            error_response = f"❌ Error: {str(e)}"
            self.state = add_message(self.state, "assistant", error_response)
            return self.state, error_response
    
    def get_state(self) -> AgentState:
        """Get current agent state."""
        return self.state or create_initial_state()
    
    def get_conversation_history(self) -> list:
        """Get conversation history."""
        return self.conversation_history
    
    def reset(self):
        """Reset the agent for a new conversation."""
        self.state = None
        self.conversation_history = []
    
    def set_origin(self, origin: str) -> Tuple[AgentState, str]:
        """
        Set the user's origin location.
        
        Args:
            origin: Location name or coordinates
        
        Returns:
            (updated_state, response_text)
        """
        if self.state is None:
            self.start_conversation()
        
        self.state.origin = origin
        
        # If we have a selected event, plan route immediately
        if self.state.selected_event and self.state.destination:
            return self.process_input(f"Plan a route from {origin} to the event")
        
        return self.state, f"Origin set to: {origin}"
    
    def set_destination(self, destination: str) -> Tuple[AgentState, str]:
        """
        Set the user's destination.
        
        Args:
            destination: Location name or coordinates
        
        Returns:
            (updated_state, response_text)
        """
        if self.state is None:
            self.start_conversation()
        
        self.state.destination = destination
        return self.state, f"Destination set to: {destination}"
    
    def set_travel_preference(self, preference: str) -> None:
        """
        Set travel preference (balanced, fastest, least_transfers).
        
        Args:
            preference: Travel preference string
        """
        if self.state is None:
            self.start_conversation()
        
        valid_prefs = ["balanced", "fastest", "least_transfers"]
        if preference in valid_prefs:
            self.state.travel_preference = preference
    
    def get_current_event(self) -> Optional[dict]:
        """Get the currently selected event as a dict."""
        if self.state and self.state.selected_event:
            return {
                "name": self.state.selected_event.name,
                "location": self.state.selected_event.location,
                "datetime": self.state.selected_event.datetime,
                "lat": self.state.selected_event.lat,
                "lon": self.state.selected_event.lon
            }
        return None
    
    def get_current_route(self) -> Optional[dict]:
        """Get the currently planned route as a dict."""
        if self.state and self.state.planned_route:
            return {
                "travel_time": self.state.planned_route.travel_time,
                "walking_time": self.state.planned_route.walking_time,
                "transfers": self.state.planned_route.transfers,
                "steps": self.state.planned_route.steps,
                "departure": self.state.planned_route.departure,
                "arrival": self.state.planned_route.arrival
            }
        return None


def create_agent(llm) -> TravelPlanningAgent:
    """
    Factory function to create a new agent.
    
    Args:
        llm: LangChain LLM instance (e.g., ChatOpenAI, OllamaLLM)
    
    Returns:
        TravelPlanningAgent instance
    """
    return TravelPlanningAgent(llm)
