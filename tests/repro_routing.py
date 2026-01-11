
from app.pipeline.routing_logic_clarification import check_guardrails_and_clarification

def test_routing():
    # Case 1: Context active -> should act 'clarification_mode'
    state_active = {
        "guardrails_blocked": False,
        "clarification_context": {
            "active": True,
            "questions": ["q1"],
            "current_index": 0
        }
    }
    result = check_guardrails_and_clarification(state_active)
    print(f"Active Context: {result} (Expected: clarification_mode)")

    # Case 2: Context inactive -> should act 'continue'
    state_inactive = {
        "guardrails_blocked": False,
        "clarification_context": {
            "active": False,
            "questions": ["q1"],
            "current_index": 0
        }
    }
    result2 = check_guardrails_and_clarification(state_inactive)
    print(f"Inactive Context: {result2} (Expected: continue)")

    # Case 3: No context -> should act 'continue'
    state_none = {
        "guardrails_blocked": False,
        "clarification_context": None
    }
    result3 = check_guardrails_and_clarification(state_none)
    print(f"None Context: {result3} (Expected: continue)")
    
    # Case 4: Guardrails blocked -> 'blocked'
    state_blocked = {
        "guardrails_blocked": True,
        "clarification_context": {"active": True}
    }
    result4 = check_guardrails_and_clarification(state_blocked)
    print(f"Blocked: {result4} (Expected: blocked)")

if __name__ == "__main__":
    test_routing()
