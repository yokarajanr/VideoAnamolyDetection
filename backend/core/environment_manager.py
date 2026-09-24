"""
core/environment_manager.py — Environment profiles and anomaly rule engine.

Defines surveillance context for different environments (lab, office, classroom, etc.).
Each environment specifies:
  - Normal expected activities
  - Anomaly types specific to that environment
  - Risk weight modifiers
  - Object watchlists

Supports both auto-inference (via VLM) and manual override.
"""

from typing import Optional
import logging

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Environment Profile Definitions
# ══════════════════════════════════════════════════════════════════════════════

ENVIRONMENT_PROFILES: dict[str, dict] = {
    "home": {
        "display_name": "Home",
        "description": "Residential home environment — family, guests, and daily activities.",
        "expected_activities": [
            "Sitting", "Walking", "Cooking", "Watching TV",
            "Family interaction", "Cleaning"
        ],
        "normal_objects": [
            "person", "chair", "couch", "tv", "laptop", "book",
            "cup", "bowl", "cat", "dog"
        ],
        "anomalies": {
            "Unauthorized Entry": "High",
            "Weapon Detection": "Critical",
            "Fire / Smoke": "Critical",
            "Person Fallen": "High",
            "Stranger Intrusion": "High",
            "Abandoned Object": "Medium",
            "Unusual Hour Activity": "Medium",
        },
        "risk_boost_classes": ["knife", "gun", "fire"],
    },

    "farming": {
        "display_name": "Farming / Agriculture",
        "description": "Agricultural environment — low traffic, crops, livestock, open fields.",
        "expected_activities": [
            "Farming", "Livestock grazing", "Tractor operation"
        ],
        "normal_objects": [
            "person", "tractor", "truck", "cow", "horse", "sheep", "dog", "bird"
        ],
        "anomalies": {
            "Unauthorized Entry": "High",
            "Predator Detected": "Critical",
            "Fire / Smoke": "Critical",
            "Poacher Activity": "Critical",
            "Livestock Breach": "Medium",
        },
        "risk_boost_classes": ["fire", "gun", "knife", "bear"],
    },

    "transportation": {
        "display_name": "Road / Transportation",
        "description": "Streets, highways, and intersections for monitoring traffic and accidents.",
        "expected_activities": [
            "Driving", "Walking on sidewalk", "Waiting at traffic light"
        ],
        "normal_objects": [
            "car", "truck", "motorcycle", "bus", "bicycle", "person", "traffic light", "stop sign"
        ],
        "anomalies": {
            "Traffic Accident / Collision": "Critical",
            "Fire / Smoke": "Critical",
            "Reckless Driving": "High",
            "Person on Highway": "Critical",
            "Abandoned Vehicle": "Medium",
        },
        "risk_boost_classes": ["fire", "person", "truck", "bus"],
    },

    "office": {
        "display_name": "Office",
        "description": "Corporate office — employees working at desks, meetings, and visitors.",
        "expected_activities": [
            "Working at desk", "Walking in corridor", "Meeting", "Printing",
            "Using computer", "Coffee break"
        ],
        "normal_objects": [
            "person", "laptop", "chair", "desk", "keyboard", "monitor",
            "cell phone", "cup", "book"
        ],
        "anomalies": {
            "Unauthorized Entry": "High",
            "Restricted Area Violation": "High",
            "Weapon Detection": "Critical",
            "Fire / Smoke": "Critical",
            "After-Hours Intrusion": "High",
            "Crowd Formation": "Medium",
            "Abandoned Object": "Medium",
            "Loitering": "Low",
        },
        "risk_boost_classes": ["knife", "gun", "fire", "backpack"],
    },

    "classroom": {
        "display_name": "Classroom",
        "description": "Educational classroom — students and teacher during lectures.",
        "expected_activities": [
            "Students sitting", "Teacher lecturing", "Note-taking",
            "Using laptop", "Group discussion", "Entering/exiting classroom"
        ],
        "normal_objects": [
            "person", "chair", "desk", "laptop", "book", "backpack",
            "cell phone", "whiteboard"
        ],
        "anomalies": {
            "Fight / Physical Altercation": "Critical",
            "Crowd Formation": "High",
            "Unauthorized Entry": "High",
            "Weapon Detection": "Critical",
            "Bullying Behavior": "High",
            "Student Fallen": "High",
            "Excessive Noise Group": "Medium",
            "Vandalism": "Medium",
        },
        "risk_boost_classes": ["knife", "gun"],
    },

    "laboratory": {
        "display_name": "Laboratory",
        "description": "Research or chemical laboratory requiring strict safety protocols.",
        "expected_activities": [
            "Conducting experiments", "Using lab equipment", "Wearing PPE",
            "Taking notes", "Chemical analysis", "Microscopy"
        ],
        "normal_objects": [
            "person", "bottle", "bowl", "scissors",
            "laptop", "chair", "desk"
        ],
        "anomalies": {
            "No PPE / Missing Safety Equipment": "High",
            "Fire / Smoke": "Critical",
            "Chemical Spill": "Critical",
            "Unauthorized Access": "High",
            "Unsafe Handling": "High",
            "Equipment Damage": "High",
            "Person Fallen": "High",
            "Abandoned Chemical": "Medium",
        },
        "risk_boost_classes": ["fire", "bottle"],
        "required_ppe": ["safety glasses", "lab coat", "gloves"],
    },

    "factory": {
        "display_name": "Factory / Industrial",
        "description": "Factory floor with heavy machinery and strict safety requirements.",
        "expected_activities": [
            "Machine operation", "Assembly work", "Material handling",
            "Quality inspection", "Maintenance", "Forklift operation"
        ],
        "normal_objects": [
            "person", "truck", "car", "motorcycle",
            "scissors", "bottle"
        ],
        "anomalies": {
            "No Helmet / No PPE": "High",
            "Unsafe Machine Operation": "Critical",
            "Restricted Zone Entry": "High",
            "Fire / Smoke": "Critical",
            "Person Fallen / Injury": "Critical",
            "Weapon Detection": "Critical",
            "Unauthorized Access": "High",
            "Equipment Malfunction Signs": "High",
        },
        "risk_boost_classes": ["fire", "person"],
        "required_ppe": ["helmet", "safety vest", "boots"],
    },

    "warehouse": {
        "display_name": "Warehouse",
        "description": "Storage warehouse — stock management, loading, and logistics.",
        "expected_activities": [
            "Stacking inventory", "Forklift operation", "Package handling",
            "Scanning barcodes", "Loading/unloading trucks"
        ],
        "normal_objects": [
            "person", "truck", "car", "backpack", "suitcase",
            "bottle", "bowl"
        ],
        "anomalies": {
            "Theft / Unauthorized Removal": "Critical",
            "Forklift Accident Risk": "Critical",
            "No Safety Vest": "High",
            "Unauthorized Access": "High",
            "Fire / Smoke": "Critical",
            "Person Fallen": "High",
            "Abandoned Object": "Medium",
        },
        "risk_boost_classes": ["fire", "truck"],
    },

    "parking": {
        "display_name": "Parking Area",
        "description": "Vehicle parking lot or garage — cars, motorcycles, and pedestrians.",
        "expected_activities": [
            "Parking vehicles", "Walking to/from vehicles",
            "Loading luggage", "Driving through"
        ],
        "normal_objects": [
            "car", "motorcycle", "truck", "bus", "bicycle",
            "person", "backpack", "suitcase"
        ],
        "anomalies": {
            "Loitering": "Medium",
            "Vehicle Break-in": "Critical",
            "Weapon Detection": "Critical",
            "Abandoned Vehicle": "Medium",
            "Reckless Driving": "High",
            "Person Fallen": "High",
            "Suspicious Activity": "High",
        },
        "risk_boost_classes": ["knife", "gun"],
    },

    "corridor": {
        "display_name": "Corridor / Hallway",
        "description": "Indoor corridor or hallway for building passage.",
        "expected_activities": [
            "Walking through", "Entering/exiting rooms",
            "Using elevator", "Brief stops"
        ],
        "normal_objects": [
            "person", "backpack", "suitcase", "cell phone"
        ],
        "anomalies": {
            "Loitering": "Medium",
            "Unauthorized Entry": "High",
            "Weapon Detection": "Critical",
            "Fight / Altercation": "Critical",
            "Abandoned Object": "Medium",
            "Person Fallen": "High",
            "After-Hours Activity": "Medium",
        },
        "risk_boost_classes": ["knife", "gun", "suitcase"],
    },

    "custom": {
        "display_name": "Custom Environment",
        "description": "User-defined environment with custom rules.",
        "expected_activities": [],
        "normal_objects": [],
        "anomalies": {},
        "risk_boost_classes": [],
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# Environment Manager Class
# ══════════════════════════════════════════════════════════════════════════════

class EnvironmentManager:
    """
    Manages the active surveillance environment profile.
    Provides context to the anomaly engine and VLM analyzer.
    """

    def __init__(self, default_env: str = "office"):
        self._current_env: str = default_env
        self._custom_overrides: dict = {}
        logger.info(f"EnvironmentManager initialized with: {default_env}")

    @property
    def current(self) -> str:
        return self._current_env

    def set_environment(self, env_key: str) -> bool:
        """Switch to a named environment. Returns False if unknown."""
        if env_key not in ENVIRONMENT_PROFILES:
            logger.warning(f"Unknown environment: {env_key}")
            return False
        self._current_env = env_key
        logger.info(f"Environment switched to: {env_key}")
        return True

    def get_profile(self, env_key: Optional[str] = None) -> dict:
        """Return the full profile dict for the given (or current) environment."""
        key = env_key or self._current_env
        profile = ENVIRONMENT_PROFILES.get(key, ENVIRONMENT_PROFILES["custom"]).copy()
        # Apply user overrides
        if key in self._custom_overrides:
            profile.update(self._custom_overrides[key])
        return profile

    def get_all_environments(self) -> list[dict]:
        """Return summary list of all available environments."""
        return [
            {
                "key": k,
                "display_name": v["display_name"],
                "description": v["description"],
            }
            for k, v in ENVIRONMENT_PROFILES.items()
        ]

    def add_custom_anomaly(self, env_key: str, anomaly_name: str, risk_level: str):
        """Add or update an anomaly rule for a given environment."""
        if env_key not in self._custom_overrides:
            self._custom_overrides[env_key] = {"anomalies": {}}
        self._custom_overrides[env_key]["anomalies"][anomaly_name] = risk_level

    def get_context_prompt(self) -> str:
        """Generate an environment context string for VLM prompts."""
        profile = self.get_profile()
        anomaly_list = "\n".join(
            f"  - {name} → {risk}"
            for name, risk in profile["anomalies"].items()
        )
        activity_list = ", ".join(profile["expected_activities"])
        return (
            f"Current surveillance environment: {profile['display_name']}\n"
            f"Description: {profile['description']}\n"
            f"Expected normal activities: {activity_list}\n"
            f"Anomaly rules for this environment:\n{anomaly_list}"
        )

    def infer_environment_from_vlm(self, vlm_description: str) -> str:
        """
        Heuristically match VLM description to a known environment.
        Returns the best-matching environment key.
        """
        desc_lower = vlm_description.lower()
        scores: dict[str, int] = {}

        keywords = {
            "home": ["sofa", "couch", "kitchen", "bedroom", "living room", "tv"],
            "farming": ["farm", "field", "crop", "livestock", "tractor", "barn", "agriculture"],
            "transportation": ["road", "street", "highway", "intersection", "traffic", "accident", "crash"],
            "office": ["desk", "monitor", "laptop", "cubicle", "conference", "whiteboard"],
            "classroom": ["students", "teacher", "lecture", "chalkboard", "school"],
            "laboratory": ["lab", "equipment", "experiment", "chemical", "microscope", "ppe"],
            "factory": ["machine", "factory", "assembly", "industrial", "conveyor", "forklift"],
            "warehouse": ["warehouse", "shelf", "shelves", "inventory", "stock", "pallet"],
            "parking": ["parking", "car", "vehicle", "garage", "lot", "motorcycle"],
            "corridor": ["hallway", "corridor", "passage", "door", "elevator"],
        }

        for env_key, kws in keywords.items():
            scores[env_key] = sum(1 for kw in kws if kw in desc_lower)

        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] > 0 else self._current_env
