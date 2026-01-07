from typing import Dict, TypedDict, List

class StateAction(TypedDict):
    state: str
    reason: str

# Defined States
INITIAL = "INITIAL"
ANSWER_PROVIDED = "ANSWER_PROVIDED"
RESOLVED = "RESOLVED"
ESCALATION_NEEDED = "ESCALATION_NEEDED"
ESCALATION_REQUESTED = "ESCALATION_REQUESTED"
AWAITING_CLARIFICATION = "AWAITING_CLARIFICATION"
SAFETY_VIOLATION = "SAFETY_VIOLATION"
EMPATHY_MODE = "EMPATHY_MODE"
BLOCKED = "BLOCKED"
LOW_CONFIDENCE = "LOW_CONFIDENCE"
STUCK_LOOP = "STUCK_LOOP"

class TransitionRule(TypedDict):
    condition_field: str  # Field in dialog_analysis to check
    condition_value: bool # Value it must match
    target_state: str     # State to transition to
    priority: int         # 1 is highest

# Signal Constants (Shared with Analysis Node)
SIGNAL_GRATITUDE = "is_gratitude"
SIGNAL_ESCALATION_REQ = "escalation_requested"
SIGNAL_QUESTION = "is_question"
SIGNAL_REPEATED = "repeated_question"
SIGNAL_FRUSTRATION = "frustration_detected"

# Strict rules mapping Analysis signals -> States
# These are evaluated in order of priority (1 = highest)
TRANSITION_RULES: List[TransitionRule] = [
    # 1. Explicit Escalation Request (Highest priority)
    {
        "condition_field": SIGNAL_ESCALATION_REQ,
        "condition_value": True,
        "target_state": ESCALATION_REQUESTED,
        "priority": 1
    },
    # 2. Gratitude -> Resolution
    {
        "condition_field": SIGNAL_GRATITUDE,
        "condition_value": True,
        "target_state": RESOLVED,
        "priority": 2
    },
    # 3. Frustration (High severity) -> Escalation
    {
        "condition_field": SIGNAL_FRUSTRATION,
        "condition_value": True,
        "target_state": ESCALATION_NEEDED,
        "priority": 3
    },
    # 4. Repeated Question -> Answer Provided (retry)
    {
        "condition_field": SIGNAL_REPEATED,
        "condition_value": True,
        "target_state": ANSWER_PROVIDED,
        "priority": 4
    },
    # 5. Generic Question -> Answer Provided (normal flow)
    {
        "condition_field": SIGNAL_QUESTION,
        "condition_value": True,
        "target_state": ANSWER_PROVIDED,
        "priority": 5
    }
]

# Config for State Machine logic
STATE_CONFIG = {
    "max_attempts": 3,
    "escalate_on_max_attempts": True
}
