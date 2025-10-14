import enum
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class ToolStatus(enum.Enum):
    success = "success"
    failure = "failure"

class ToolResult:
    def __init__(self, status: ToolStatus, data: Dict[str, Any] | None = None, error_message: str | None = None):
        self.status = status
        self.data = data or {}
        self.error_message = error_message

class ToolRegistry:
    """
    Minimal tool registry to support Orchestrator tool calls.
    Currently supports: image_generation
    """

    def __init__(self) -> None:
        pass

    def execute_tool_sync(self, tool_name: str, params: Dict[str, Any]) -> ToolResult:
        try:
            if tool_name == "image_generation":
                from src.video.image_generator import ImageGenerator
                prompt = params.get("prompt") or params.get("description") or "abstract tech illustration"
                gen = ImageGenerator()
                img = gen.generate_image_with_api(prompt)
                # Save to temp file for renderer consumption path
                out_path = gen.save_temp_image(img)
                return ToolResult(ToolStatus.success, {"image_path": out_path})
            else:
                logger.warning(f"Unknown tool: {tool_name}")
                return ToolResult(ToolStatus.failure, error_message=f"unknown tool {tool_name}")
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}: {e}")
            return ToolResult(ToolStatus.failure, error_message=str(e))

