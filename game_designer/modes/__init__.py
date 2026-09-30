"""Interaction modes package for Jarvis Game Designer."""

from game_designer.modes.advisor_mode import AdvisorMode
from game_designer.modes.analysis_mode import AnalysisMode
from game_designer.modes.base_mode import BaseMode
from game_designer.modes.brainstorm_mode import BrainstormMode
from game_designer.modes.briefing_mode import BriefingMode
from game_designer.modes.compare_mode import CompareMode
from game_designer.modes.gdd_mode import GDDMode
from game_designer.modes.market_mode import MarketMode
from game_designer.modes.qa_mode import QAMode

MODES_REGISTRY: dict[str, BaseMode] = {
    "qa": QAMode(),
    "analyze_game": AnalysisMode(),
    "brainstorm": BrainstormMode(),
    "compare": CompareMode(),
    "create_gdd": GDDMode(),
    "brief": BriefingMode(),
    "advise": AdvisorMode(),
    "market_analysis": MarketMode(),
}

# Kolay erişim ve geriye dönük uyumluluk takma adları
MODES_REGISTRY["analysis"] = MODES_REGISTRY["analyze_game"]
MODES_REGISTRY["gdd"] = MODES_REGISTRY["create_gdd"]
MODES_REGISTRY["briefing"] = MODES_REGISTRY["brief"]
MODES_REGISTRY["advisor"] = MODES_REGISTRY["advise"]
MODES_REGISTRY["market"] = MODES_REGISTRY["market_analysis"]

__all__ = [
    "BaseMode",
    "QAMode",
    "AnalysisMode",
    "BrainstormMode",
    "CompareMode",
    "GDDMode",
    "BriefingMode",
    "AdvisorMode",
    "MarketMode",
    "MODES_REGISTRY",
]
