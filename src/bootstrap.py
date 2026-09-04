"""
Application bootstrap for Athena.

Responsible for constructing and wiring together all application
components.
"""

from core.assistant import Athena

from tools.registry import ToolRegistry
from tools.manager import ToolManager

from tools.calculator.tool import CalculatorTool
from tools.datetime.tool import DateTimeTool
from tools.files.tool import FileTool
from tools.search.tool import SearchTool
from tools.web.tool import WebTool
from tools.os.tool import OSTool


def create_athena() -> Athena:
    """
    Build and return the Athena application.
    """

    # Create the tool registry
    registry = ToolRegistry()

    # Register all available tools.
    #
    # Order matters where tools share overlapping trigger words:
    #   - SearchTool before WebTool: SearchTool's colon-prefixed
    #     triggers ("search:", "look up:") don't actually collide
    #     with WebTool's space-based phrase matching, but registering
    #     it first keeps intent unambiguous as both evolve.
    #   - FileTool before WebTool: both react to "look for"/"find",
    #     but FileTool should win whenever "file"/"files" is
    #     explicitly mentioned.
    #   - WebTool before OSTool: both react to "open <something>",
    #     but WebTool should win for domain-shaped text (e.g.
    #     "open google.com") before OSTool tries to treat it as an
    #     installed application name.
    registry.register(CalculatorTool())
    registry.register(DateTimeTool())
    registry.register(FileTool())
    registry.register(SearchTool())
    registry.register(WebTool())
    registry.register(OSTool())

    # Create the tool manager
    tool_manager = ToolManager(registry)

    # Create the Athena application
    athena = Athena(tool_manager)

    return athena