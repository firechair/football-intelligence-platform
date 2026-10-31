"""Asks the agent one question from the command line. Run from the platform/ folder.

The agent was never connected to the product's interface. This script is new, and repeats the
steps of the original endpoint: compliance check, orchestrator, response filter.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.compliance_service import ComplianceService
from app.services.function_calling_orchestrator import FunctionCallingOrchestrator


async def main(question: str) -> int:
    compliance = ComplianceService()
    check = await compliance.check_user_message(question, user_id="demo")
    if check["should_block"]:
        print(check["intervention_message"])
        return 0

    result = await FunctionCallingOrchestrator().process_message(question, user_id="demo")
    for call in result["tool_calls_made"]:
        print(f"→ tool {call['tool']}({call['arguments']})")
    reply, _ = await compliance.filter_ai_response(result["reply"], user_id="demo")
    print(reply)
    return 1 if result["metadata"].get("error") else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question")
    sys.exit(asyncio.run(main(parser.parse_args().question)))
