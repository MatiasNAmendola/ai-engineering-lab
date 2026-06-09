#!/usr/bin/env python3
"""
03_agent_runtime_scratch.py

Karpathy-style, zero-dependency implementation of an Agent Runtime.
Demonstrates:
1. ReAct Loop (Reason -> Tool Action -> Observation).
2. Event Bus (Pub-Sub pattern for decoupled messaging).
3. Task Scheduler (non-blocking simulation).
4. Memory Engine (Short-term context + simulated Vector Long-term consolidate).
5. Context Propagation (carrying trace metadata implicitly).
"""

import time
import uuid
from typing import Dict, Any, List, Callable, Optional, Tuple


# --- 1. CONTEXT PROPAGATION ENGINE ---

class ExecutionContext:
    """
    Propagates tracing metadata (trace_id, parent_span_id, and tenant parameters)
    down the execution tree. Similar to OpenTelemetry context propagation.
    """
    def __init__(
        self, 
        trace_id: Optional[str] = None, 
        parent_span_id: Optional[str] = None,
        tenant_id: str = "default_tenant"
    ):
        self.trace_id = trace_id or str(uuid.uuid4())
        self.parent_span_id = parent_span_id
        self.tenant_id = tenant_id

    def spawn_child(self) -> "ExecutionContext":
        """Spawns a child context with the current trace_id and a new span link."""
        return ExecutionContext(
            trace_id=self.trace_id,
            parent_span_id=str(uuid.uuid4())[:8],
            tenant_id=self.tenant_id
        )

    def __str__(self) -> str:
        return f"[Trace={self.trace_id[:8]} | Span={self.parent_span_id or 'ROOT'} | Tenant={self.tenant_id}]"


# --- 2. EVENT BUS ---

class EventBus:
    """A simple synchronous publisher-subscriber event hub."""
    def __init__(self):
        self.listeners: Dict[str, List[Callable[[Dict[str, Any], ExecutionContext], None]]] = {}

    def subscribe(self, event_type: str, callback: Callable[[Dict[str, Any], ExecutionContext], None]):
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(callback)

    def publish(self, event_type: str, payload: Dict[str, Any], context: ExecutionContext):
        # Implicitly capture timestamp
        payload["timestamp"] = time.time()
        if event_type in self.listeners:
            for listener in self.listeners[event_type]:
                listener(payload, context)


# --- 3. SCHEDULER ---

class TaskScheduler:
    """A simple task queue executor that manages sequential/deferred operations."""
    def __init__(self):
        self.queue: List[Tuple[Callable, List[Any], Dict[str, Any]]] = []

    def schedule(self, fn: Callable, *args, **kwargs):
        self.queue.append((fn, list(args), kwargs))

    def run_all(self):
        print(f"[{self.__class__.__name__}] Executing {len(self.queue)} scheduled tasks...")
        while self.queue:
            fn, args, kwargs = self.queue.pop(0)
            fn(*args, **kwargs)


# --- 4. MEMORY ENGINE ---

class MemoryEngine:
    """
    A hybrid memory store.
    - Short-term: Conversational message list.
    - Long-term: Key-value consolidate index (simulating consolidated experiences).
    """
    def __init__(self):
        self.short_term: List[Dict[str, str]] = []
        self.long_term: Dict[str, Any] = {}

    def add_message(self, role: str, content: str):
        self.short_term.append({"role": role, "content": content})

    def consolidate(self, key: str, synthesis: str):
        """Saves a consolidated summary to simulated vector long-term memory."""
        self.long_term[key] = {
            "synthesis": synthesis,
            "consolidated_at": time.time()
        }

    def recall(self, query_keyword: str) -> Optional[str]:
        """Recalls relevant information from long-term memory."""
        for key, value in self.long_term.items():
            if query_keyword.lower() in key.lower():
                return value["synthesis"]
        return None


# --- 5. AGENT RUNTIME & REACT LOOP ---

class AgentRuntime:
    def __init__(self, name: str, event_bus: EventBus):
        self.name = name
        self.event_bus = event_bus
        self.memory = MemoryEngine()
        self.tools: Dict[str, Tuple[Callable[[str, ExecutionContext], str], str]] = {}

    def register_tool(self, name: str, description: str, fn: Callable[[str, ExecutionContext], str]):
        self.tools[name] = (fn, description)

    def execute_tool_with_propagation(self, tool_name: str, args: str, context: ExecutionContext) -> str:
        """Executes a tool within a child tracing context."""
        child_context = context.spawn_child()
        
        self.event_bus.publish(
            "tool_call_started", 
            {"tool": tool_name, "args": args}, 
            child_context
        )
        
        if tool_name not in self.tools:
            result = f"Error: Tool '{tool_name}' not found."
        else:
            tool_fn, _ = self.tools[tool_name]
            try:
                result = tool_fn(args, child_context)
            except Exception as e:
                result = f"Error during tool execution: {str(e)}"
                
        self.event_bus.publish(
            "tool_call_completed", 
            {"tool": tool_name, "result": result}, 
            child_context
        )
        return result

    def run(self, user_goal: str, context: ExecutionContext) -> str:
        """
        Executes a deterministic ReAct loop mimicking LLM thought cycles:
        Thought -> Action (Tool Call) -> Observation -> Final Answer.
        """
        self.event_bus.publish("agent_started", {"goal": user_goal}, context)
        self.memory.add_message("user", user_goal)
        
        print(f"\n[{self.name}] Initiating ReAct Loop for goal: '{user_goal}'")
        
        # Step 1: Reason / Check Long-term memory
        print("  Thought 1: Check memory database for facts related to user request.")
        recall_fact = self.memory.recall("database")
        
        if recall_fact:
            print(f"  Observation 1: Retrieved from Long-term Memory: '{recall_fact}'")
            # Act with retrieved fact
            action_args = f"db_uri=postgres://localhost:5432/prod, query='{recall_fact}'"
        else:
            print("  Observation 1: No long-term memories found. Checking config system.")
            action_args = "config_key=db_connection"
            
        # Step 2: Execute Action (Tool calling)
        print("  Thought 2: Call 'fetch_database_config' to obtain connection string.")
        tool_result = self.execute_tool_with_propagation("fetch_database_config", action_args, context)
        print(f"  Observation 2: Tool execution result: '{tool_result}'")
        
        # Step 3: Final output formulation
        final_answer = f"Database status verified. Connection verified using parameters: {tool_result}."
        self.memory.add_message("assistant", final_answer)
        
        self.event_bus.publish("agent_completed", {"answer": final_answer}, context)
        return final_answer


# --- SAMPLE TOOLS ---

def fetch_database_config_tool(args: str, context: ExecutionContext) -> str:
    """Simulated systems configuration retrieval tool."""
    print(f"    [Tool: fetch_database_config] Running... {context}")
    # Simulate DB details retrieval
    return f"host=127.0.0.1;port=5432;db=production_core;tenant={context.tenant_id}"


# --- RUNNER & EVENT MONITOR ---

def run_agent_runtime_demo():
    print("=== AI Engineering Lab: Agent Runtime & Loop ===")
    
    # Initialize infrastructure
    event_bus = EventBus()
    scheduler = TaskScheduler()
    
    # Define Event Listeners (Observability Hooks)
    def log_agent_lifecycle(payload: Dict[str, Any], context: ExecutionContext):
        print(f"  📡 [Bus Event] Lifecycle: {payload} {context}")
        
    def log_tool_lifecycle(payload: Dict[str, Any], context: ExecutionContext):
        print(f"  📡 [Bus Event] Tool Event: {payload} {context}")

    event_bus.subscribe("agent_started", log_agent_lifecycle)
    event_bus.subscribe("agent_completed", log_agent_lifecycle)
    event_bus.subscribe("tool_call_started", log_tool_lifecycle)
    event_bus.subscribe("tool_call_completed", log_tool_lifecycle)
    
    # Initialize Agent
    agent = AgentRuntime("PhoenixAgent", event_bus)
    agent.register_tool("fetch_database_config", "Gets DB configuration info", fetch_database_config_tool)
    
    # Consolidate a long-term memory experience beforehand
    agent.memory.consolidate(
        key="database setup history",
        synthesis="Production DB utilizes SSL connection parameters"
    )
    
    # Set up Execution Context (Tenant-scoped tracking)
    root_context = ExecutionContext(tenant_id="enterprise_client_alpha")
    
    # Schedule agent execution as a task
    scheduler.schedule(agent.run, user_goal="Verify database status.", context=root_context)
    
    # Run the scheduler
    scheduler.run_all()

if __name__ == "__main__":
    run_agent_runtime_demo()
