"""
Graph Builder for RAG Pipeline.
Constructs the actual LangGraph StateGraph based on configuration.
"""
from langgraph.graph import StateGraph, START, END
from app.pipeline.state import State
from app.pipeline.node_registry import NODE_FUNCTIONS
from app.pipeline.routing_logic import (
    cache_hit_logic, 
    router_logic, 
    should_fast_escalate, 
    check_guardrails_outcome
)
from app.pipeline.routing_logic_clarification import route_after_retrieval, check_guardrails_and_clarification
from app.pipeline.validators import validate_pipeline_structure
from app.services.config_loader.loader import load_pipeline_config, get_node_enabled
from app.pipeline.schema_generator import generate_node_schema
from app.observability.pipeline_logger import pipeline_logger

def build_graph():
    """
    Builds and constructs the LangGraph StateGraph workflow.
    
    This function:
    1. Initializes StateGraph with the State schema.
    2. Adds infrastructure nodes (Cache) if enabled.
    3. Loads pipeline configuration and adds active nodes.
    4. Validates the resulting pipeline structure.
    5. Connects all nodes with edges (sequential, conditional, and special branches).
    6. Compiles and returns the final graph.

    Returns:
        langgraph.graph.CompiledGraph: The compiled RAG pipeline workflow
    """
    
    workflow = StateGraph(State)

    # CACHE LAYER: Always add cache nodes if enabled
    cache_enabled = get_node_enabled("check_cache")
    if cache_enabled:
        # Generate schemas for cache nodes
        check_cache_schema = generate_node_schema("check_cache", NODE_FUNCTIONS["check_cache"])
        store_cache_schema = generate_node_schema("store_in_cache", NODE_FUNCTIONS["store_in_cache"])
        
        workflow.add_node("check_cache", NODE_FUNCTIONS["check_cache"], input_schema=check_cache_schema)
        pipeline_logger.log_node_added("check_cache")
        workflow.add_node("store_in_cache", NODE_FUNCTIONS["store_in_cache"], input_schema=store_cache_schema)
        pipeline_logger.log_node_added("store_in_cache")

    # Get pipeline nodes from config
    config = load_pipeline_config()
    pipeline_config = config.get("pipeline", config.get("nodes", []))

    # Identify active nodes preserving config order
    active_node_names = [
        n["name"] for n in pipeline_config 
        if n.get("enabled", False)
    ]
    
    # Log config loaded
    pipeline_logger.log_config_loaded(len(active_node_names))

    # Validate structure
    validate_pipeline_structure(active_node_names)

    # Add active nodes to workflow
    for name in active_node_names:
        if name in NODE_FUNCTIONS and name not in ["check_cache", "store_in_cache"]:
            pipeline_logger.log_node_added(name)
            # Generate schema for this node
            node_schema = generate_node_schema(name, NODE_FUNCTIONS[name])
            workflow.add_node(name, NODE_FUNCTIONS[name], input_schema=node_schema)
        elif name not in NODE_FUNCTIONS:
             pipeline_logger.warning(f"Node {name} enabled in config but missing in NODE_FUNCTIONS")

    # --- CONNECT EDGES ---

    start_node = START
    
    # Security: input_guardrails MUST run BEFORE cache check
    input_guardrails_enabled = "input_guardrails" in active_node_names

    # 1. Determine Start Node Sequence
    if "session_starter" in active_node_names:
        workflow.add_edge(START, "session_starter")
        pipeline_logger.log_edge_added("START", "session_starter")
        # After session: guardrails first, then cache
        if input_guardrails_enabled:
            workflow.add_edge("session_starter", "input_guardrails")
            pipeline_logger.log_edge_added("session_starter", "input_guardrails")
            start_node = "input_guardrails"
        elif cache_enabled:
            workflow.add_edge("session_starter", "check_cache")
            pipeline_logger.log_edge_added("session_starter", "check_cache")
            start_node = "check_cache"
        else:
            start_node = "session_starter"
    elif input_guardrails_enabled:
        workflow.add_edge(START, "input_guardrails")
        pipeline_logger.log_edge_added("START", "input_guardrails")
        start_node = "input_guardrails"
    elif cache_enabled:
        workflow.add_edge(START, "check_cache")
        pipeline_logger.log_edge_added("START", "check_cache")
        start_node = "check_cache"

    # Filter pipeline nodes (excluding infrastructure nodes already handled)
    pipeline_nodes = [
        n for n in active_node_names 
        if n not in ["session_starter", "check_cache", "store_in_cache", "archive_session", "input_guardrails"]
    ]

    if pipeline_nodes:
        first_pipeline_node = pipeline_nodes[0]
        
        # Connect input_guardrails → cache/state_machine/pipeline
        if input_guardrails_enabled:
            target_if_blocked = "state_machine" if "state_machine" in active_node_names else first_pipeline_node
            
            # Determine target for normal continuation
            target_continue = "check_cache" if cache_enabled else first_pipeline_node

            # Select routing logic (support clarification bypass if enabled)
            if "clarification_questions" in active_node_names:
                gw_logic = check_guardrails_and_clarification
                gw_map = {
                    "blocked": target_if_blocked,
                    "clarification_mode": "clarification_questions",
                    "continue": target_continue
                }
            else:
                gw_logic = check_guardrails_outcome
                gw_map = {
                    "blocked": target_if_blocked,
                    "continue": target_continue
                }

            workflow.add_conditional_edges("input_guardrails", gw_logic, gw_map)
            pipeline_logger.log_conditional_edge_added("input_guardrails", gw_logic.__name__, gw_map)

            if cache_enabled:
                # Cache logic
                workflow.add_conditional_edges(
                    "check_cache",
                    cache_hit_logic,
                    {
                        "store_in_cache": "store_in_cache",
                        "miss": first_pipeline_node
                    }
                )
                pipeline_logger.log_conditional_edge_added("check_cache", "cache_hit_logic", {"store_in_cache": "store_in_cache", "miss": first_pipeline_node})

        elif cache_enabled:
            # No guardrails, just cache
            workflow.add_conditional_edges(
                "check_cache",
                cache_hit_logic,
                {
                    "store_in_cache": "store_in_cache",
                    "miss": first_pipeline_node
                }
            )
            pipeline_logger.log_conditional_edge_added("check_cache", "cache_hit_logic", {"store_in_cache": "store_in_cache", "miss": first_pipeline_node})
        elif start_node == START and "session_starter" not in active_node_names:
            # Direct start to first node if nothing else
            workflow.add_edge(START, first_pipeline_node)
            pipeline_logger.log_edge_added("START", first_pipeline_node)
        
        # Connect Pipeline Nodes sequentially
        for i in range(len(pipeline_nodes) - 1):
            current_node = pipeline_nodes[i]
            next_node = pipeline_nodes[i+1]

            # Special logic: Early exit after dialog_analysis
            if current_node == "dialog_analysis" and "state_machine" in active_node_names:
                normal_next_node = next_node
                
                workflow.add_conditional_edges(
                    "dialog_analysis",
                    should_fast_escalate,
                    {
                        "fast_escalate": "state_machine",
                        "continue": normal_next_node
                    }
                )
                pipeline_logger.log_conditional_edge_added("dialog_analysis", "should_fast_escalate", {"fast_escalate": "state_machine", "continue": normal_next_node})
            # Special logic for routing if it's in the middle
            elif current_node == "routing":
                if "generation" in pipeline_nodes:
                    target = "prompt_routing" if "prompt_routing" in active_node_names else "generation"
                    target_exit = "archive_session" if "archive_session" in active_node_names else ("store_in_cache" if cache_enabled else END)
                    
                    workflow.add_conditional_edges(
                        "routing",
                        router_logic,
                        {
                            "generation": target,
                            END: target_exit
                        }
                    )
                    pipeline_logger.log_conditional_edge_added("routing", "router_logic", {"generation": target, "END": target_exit})
                else:
                    target_exit = "archive_session" if "archive_session" in active_node_names else ("store_in_cache" if cache_enabled else END)
                    workflow.add_edge("routing", target_exit)
                    pipeline_logger.log_edge_added("routing", target_exit)
            # Special logic: state_machine always to routing if present
            elif current_node == "state_machine" and "routing" in active_node_names:
                workflow.add_edge("state_machine", "routing")
                pipeline_logger.log_edge_added("state_machine", "routing")
            # Special logic: Clarification Flow (Phase 1)
            elif next_node == "clarification_questions":
                # Determine skip target (node after clarification)
                if i + 2 < len(pipeline_nodes):
                    skip_target = pipeline_nodes[i+2]
                else:
                    # Fallback if clarification is last 
                    if "archive_session" in active_node_names:
                        skip_target = "archive_session"
                    elif cache_enabled:
                         skip_target = "store_in_cache"
                    else:
                         skip_target = END
                
                workflow.add_conditional_edges(
                    current_node,
                    route_after_retrieval,
                    {
                        "clarification_questions": "clarification_questions",
                        "continue": skip_target
                    }
                )
                pipeline_logger.log_conditional_edge_added(current_node, "route_after_retrieval", {"clarification": "clarification_questions", "continue": skip_target})
            else:
                workflow.add_edge(current_node, next_node)
                pipeline_logger.log_edge_added(current_node, next_node)

        # Handle End of Pipeline
        last_node = pipeline_nodes[-1]
        if last_node != "routing":
            if "archive_session" in active_node_names:
                workflow.add_edge(last_node, "archive_session")
                pipeline_logger.log_edge_added(last_node, "archive_session")
            elif cache_enabled:
                workflow.add_edge(last_node, "store_in_cache")
                pipeline_logger.log_edge_added(last_node, "store_in_cache")
            else:
                workflow.add_edge(last_node, END)
                pipeline_logger.log_edge_added(last_node, "END")
                  
        # Ensure archive_session has an exit path
        if "archive_session" in active_node_names:
            if cache_enabled:
                workflow.add_edge("archive_session", "store_in_cache")
                pipeline_logger.log_edge_added("archive_session", "store_in_cache")
            else:
                workflow.add_edge("archive_session", END)
                pipeline_logger.log_edge_added("archive_session", "END")
    else:
        # No pipeline nodes (rare edge case)
        if cache_enabled:
            workflow.add_conditional_edges(
                "check_cache",
                cache_hit_logic,
                {
                    "store_in_cache": "store_in_cache",
                    "miss": END 
                }
            )
            pipeline_logger.log_conditional_edge_added("check_cache", "cache_hit_logic", {"store_in_cache": "store_in_cache", "miss": "END"})

    # Cache Store always goes to END
    if cache_enabled:
        workflow.add_edge("store_in_cache", END)
        pipeline_logger.log_edge_added("store_in_cache", "END")

    return workflow.compile()
